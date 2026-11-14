from copy import deepcopy
from dataclasses import asdict
from random import Random

from actions.contracts import ActionName, CommandResult, DefenderCommand, TargetedAction
from actions.defender_action_encoding import (
    build_defender_action_choices,
    decode_action_choice,
)
from actions.defender_actions import (
    advance_defender_jobs,
    start_defender_action,
    start_validated_defender_action,
    validate_defender_action,
)
from attacker.intrusion import apply_due_intrusion
from attacker.scripted_attacker import advance_attack_jobs, start_attack_jobs
from observations.contracts import DefenderObservation, ObservationVector
from observations.defender_observation import build_defender_observation
from observations.defender_observation_encoding import ObservationEncoder
from observations.monitoring import update_monitoring
from rewards.contracts import RewardResult
from rewards.shared_reward import calculate_reward
from workload.file_requests import build_required_requests, run_file_requests
from world.episode_script import (
    apply_due_outages,
    draw_episode_script,
    episode_rngs,
)
from world.layout import WorldLayout
from world.results import WorldStepReport
from world.state import (
    FileRequestResult,
    MonitoringWarning,
    WorldState,
    create_initial_state,
)


class WorldEnvironment:

    def __init__(self, settings: dict) -> None:

        settings = deepcopy(settings)
        self._config = settings["world"]
        self._action_config = settings["actions"]
        self._attacker_config = settings["attacker"]
        self._workload_config = settings["workload"]
        self._observation_config = settings["observations"]
        self._reward_config = settings["rewards"]
        
        self._layout = WorldLayout.from_config(self._config)

        # a placeholder seed, the run replaces it through set_world_rng()
        self.set_world_rng(0)
        
        # an action-choice tuple each for each defender.
        self._action_choices = {
            defender_id: build_defender_action_choices(self._config, defender_id)
            for defender_id in self._layout.defender_ids
        }
        
        self._required_requests = tuple(build_required_requests(self._config, self._workload_config))
        
        # an observation encoder each for each defender.
        self._encoders = {
            defender_id: ObservationEncoder(
                self._layout.servers[defender_id], 
                self._config["episode"]["max_steps"],
                max(self._action_config["duration_steps"].values()),
                )
            for defender_id in self._layout.defender_ids
        }
        

        self.reset()



    def get_defender_ids(self) -> tuple[str, ...]:
        return self._layout.defender_ids

    def is_defender_free(self, defender_id: str) -> bool:
        if not isinstance(defender_id, str):
            raise TypeError("defender_id must be a string")
        if defender_id not in self.state.defenders:
            raise ValueError(f"Unknown defender_id: {defender_id!r}")
        
        return self.state.defenders[defender_id].job is None

    def is_episode_finished(self) -> bool:
        return self.state.elapsed_steps >= self._config["episode"]["max_steps"]

    def reset(self) -> None:


        episode_random_events_rngs = episode_rngs(self._world_seed, self._episodes_started)
        
        script = draw_episode_script(self._config, 
                                     self._observation_config, 
                                     self._world_rng,
                                     episode_random_events_rngs)
        
        self._episodes_started += 1

        self.state: WorldState = create_initial_state(self._config, script)

    def set_world_rng(self, seed: int) -> None:
        
        if type(seed) is not int:
            raise TypeError("seed must be an integer")

        self._world_seed = seed
        self._world_rng = Random(seed)
        self._episodes_started = 0



    @property
    def world_seed(self) -> int | None:
        
        if "intrusion" in self._config or "outages" in self._config or "warnings" in self._observation_config:
            return self._world_seed
        
        return None



    def step(self, defender_commands: dict[str, DefenderCommand]) -> WorldStepReport:
        
        if self.is_episode_finished():
            raise RuntimeError("Episode finished; call reset() before another step")

        if not isinstance(defender_commands, dict):
            raise TypeError("defender_commands must be a dictionary")
        for defender_id, command in defender_commands.items():
            if not isinstance(command, tuple):
                raise TypeError("Each command must be an (action, target) tuple")
            if len(command) != 2:
                raise ValueError("Each command must contain exactly action and target")
            
            action, target = command
            validate_defender_action(self.state, self._action_config, 
                                     defender_id, action, target)
            
        #check if all defenders free at start of interval are being assigned a command.
        missing = [
            defender_id
            for defender_id, defender in self.state.defenders.items()
            if defender.job is None and defender_id not in defender_commands
        ]
        if missing:
            raise ValueError(f"Missing commands for free defenders: {missing}")

        # first, a due intrusion infects its server, so its spread can start in this interval,
        # and the scripted outages stop or restart their servers' services.
        intrusion = apply_due_intrusion(self.state)
        outages_started = apply_due_outages(self.state)

        # then, attacks are started.
        attacks_started = self.start_attacks()

        # then, start defender action from the argument defender_commands and collect whether they get accepted.
        defender_command_results = {}
        target_states_at_start = {}
        inspection_start_count = 0
        for defender_id in self.state.defenders:
            target_states_at_start[defender_id] = None
            if defender_id in defender_commands:
                
                action, target = defender_commands[defender_id]

                target_state = None
                if target is not None:
                    host = self.state.hosts[target]
                    target_state = {"compromised": host.compromised,
                                    "isolated": host.isolated,
                                    "service_running": host.file_service_running,
                                    "vulnerable": host.vulnerable}
                
                defender_command_results[defender_id] = start_validated_defender_action(self.state, 
                                                                                        self._action_config, 
                                                                                        defender_id, 
                                                                                        action, 
                                                                                        target)
                if defender_command_results[defender_id] == "accepted":
                    target_states_at_start[defender_id] = target_state
                if action == "inspect" and defender_command_results[defender_id] == "accepted":
                    inspection_start_count += 1


        defender_completions = self.advance_defenders()
        attack_completions = self.advance_attacks()

        # Ordinary work sees the host conditions after this interval's effects.
        request_results = self.run_workload()

        # deliver due local evidence for the upcoming boundary S_(t+1).
        monitoring_deliveries = self.update_monitoring()

       
        for defender_id, defender in self.state.defenders.items():
            if defender_id in defender_completions:
                defender.last_command_feedback = "completed"
            else:
                defender.last_command_feedback = defender_command_results.get(defender_id, "none")

        
        # Score final truth/work and this interval's newly started inspections.
        reward = self.calculate_reward(inspection_start_count)
        
        #after all this, increment clock/timer.
        self.state.elapsed_steps += 1
        
        
        return {
            "elapsed_steps": self.state.elapsed_steps,
            "intrusion": intrusion,
            "outages_started": outages_started,
            "defender_command_results": defender_command_results,
            "target_states_at_start": target_states_at_start,
            "defender_completions": defender_completions,
            "attacks_started": attacks_started,
            "attack_completions": attack_completions,
            "request_results": [asdict(result) for result in request_results],
            "monitoring_deliveries": {
                defender_id: {host_id: asdict(warning) for host_id, warning in warnings.items()}
                for defender_id, warnings in monitoring_deliveries.items()
            },
            "reward": reward,
            
            # Every server's hidden truth at the end of the interval, for run records and timelines.
            "servers": {
                host_id: {"compromised": host.compromised,
                          "isolated": host.isolated,
                          "service_running": host.file_service_running,
                          "vulnerable": host.vulnerable}
                for host_id, host in self.state.hosts.items() if host.has_file_service
            },
            "episode_finished": self.is_episode_finished(),
        }



    def configuration_snapshot(self) -> dict[str, dict]:
        
    
        return deepcopy({"world": self._config, 
                         "actions": self._action_config, 
                         "attacker": self._attacker_config, 
                         "workload": self._workload_config, 
                         "observations": self._observation_config, 
                         "rewards": self._reward_config,})



    def observe(self, defender_id: str) -> DefenderObservation:
        return build_defender_observation(self.state, 
                                          self._config, 
                                          self._observation_config, 
                                          defender_id, 
                                          layout=self._layout)



    def encode_observation(self, defender_id: str) -> ObservationVector:
        return self.encode(defender_id, self.observe(defender_id))


    def encode(self, defender_id: str, observation: DefenderObservation) -> ObservationVector:
        return self._encoders[defender_id].encode(observation)



    def action_choices(self, defender_id: str) -> tuple[tuple[ActionName, str | None], ...]:
        
        if not isinstance(defender_id, str):
            raise TypeError("defender_id must be a string")
        if defender_id not in self._action_choices:
            raise ValueError(f"Unknown defender_id: {defender_id!r}")
        
        return self._action_choices[defender_id]


    def decode_action(self, defender_id: str, action_id: int) -> tuple[ActionName, str | None]:
        return decode_action_choice(self.action_choices(defender_id), action_id)



    def start_action(self, 
                     defender_id: str, 
                     action: ActionName, 
                     target: str | None = None) -> CommandResult:
        return start_defender_action(self.state, 
                                     self._action_config, 
                                     defender_id, action, 
                                     target)



    def start_attacks(self) -> dict[str, str]:
        return start_attack_jobs(self.state, self._config, self._attacker_config,
                                 partners=self._layout.partners)



    def advance_attacks(self) -> dict[str, str]:
        return advance_attack_jobs(self.state, self._config, partners=self._layout.partners)



    def advance_defenders(self) -> dict[str, TargetedAction]:
        completed = advance_defender_jobs(self.state, self._action_config)
        return completed



    def run_workload(self) -> list[FileRequestResult]:
        return run_file_requests(self.state, self._config, self._workload_config,
                                 required_requests=self._required_requests)


    def update_monitoring(self) -> dict[str, dict[str, MonitoringWarning]]:
        return update_monitoring(self.state, self._observation_config)


    def calculate_reward(self, inspection_start_count: int) -> RewardResult:
        return calculate_reward(self.state, self._reward_config, inspection_start_count)
