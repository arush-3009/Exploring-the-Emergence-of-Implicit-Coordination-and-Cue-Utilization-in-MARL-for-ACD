import random
from collections.abc import Callable
from dataclasses import dataclass

from observations.contracts import DefenderObservation, ObservationVector
from world.environment_interface import EnvironmentInterface
from world.results import BoundaryResult, WorldStepReport

Policy = Callable[[ObservationVector], int]


@dataclass
class EpisodeLog:


    observations: list[dict[str, ObservationVector]]  # each defender's vector at S_t
    action_ids: list[dict[str, int | None]]  # chosen ID; None while busy
    shared_rewards: list[float]  # team reward for S_t -> S_(t+1)
    total_episode_reward: float  # sum of shared_rewards, no discounting
    final_observations: dict[str, ObservationVector]  # each defender's vector at the last boundary
    observation_facts: list[dict[str, DefenderObservation]]  # the named facts each vector at S_t was encoded from
    final_observation_facts: dict[str, DefenderObservation]  # the same at the last boundary

    # Hidden truth for checking and evaluation.
    
    world_reports: list[WorldStepReport]  # full world step report for interval t
    script: dict  # the episode's drawn events (world.state.EpisodeScript as a dict)


class EpisodeRunner:


    def __init__(self, interface: EnvironmentInterface, policies: dict[str, Policy]) -> None:
        
        if not isinstance(policies, dict):
            raise TypeError("policies must be a dictionary")
        for policy in policies.values():
            if not callable(policy):
                raise TypeError("Each policy must be callable")
            
            
        self._interface = interface
        self._policies = policies



    def _choose_actions(self, boundary: BoundaryResult) -> dict[str, int]:

        free_defenders_chosen_action_ids = {}
        for defender_id in boundary["defenders_to_act"]:
            observation = boundary["observations"][defender_id].copy()
            free_defenders_chosen_action_ids[defender_id] = self._policies[defender_id](observation)
        return free_defenders_chosen_action_ids




    def run(self) -> EpisodeLog:


        #boundary is the left state boundary for a time interval. So, for interval
        # Sₜ → Sₜ₊₁, the boundary would be the state information and resulting observations at Sₜ.
        boundary = self._interface.reset()

        if set(self._policies) != set(boundary["observations"]):
            raise ValueError("Provide exactly one policy for each defender")

        script = boundary["script"]
        observations = []
        observation_facts = []
        action_ids = []
        shared_rewards = []
        world_reports = []

        while not boundary["episode_finished"]:
            
            free_defenders_chosen_action_ids = self._choose_actions(boundary)

            #advances 1 interval. EnvironmentInterface.step returns a dictionary of
            #the state/information of the WorldEnvrionment.state at the next 
            #boundary, i.e. start of the next interval.
            next_boundary = self._interface.step(free_defenders_chosen_action_ids)


            all_defenders_recorded_action_ids = {
                defender_id: free_defenders_chosen_action_ids.get(defender_id)
                for defender_id in boundary["observations"]
            }

            observations.append(boundary["observations"])
            observation_facts.append(boundary["observation_facts"])
            action_ids.append(all_defenders_recorded_action_ids)
            shared_rewards.append(next_boundary["shared_reward"])
            world_reports.append(next_boundary["world_report"])

            boundary = next_boundary


        return EpisodeLog(
            observations=observations,
            action_ids=action_ids,
            shared_rewards=shared_rewards,
            total_episode_reward=sum(shared_rewards),
            final_observations=boundary["observations"],
            observation_facts=observation_facts,
            final_observation_facts=boundary["observation_facts"],
            world_reports=world_reports,
            script=script,
        )






def evaluation_seeds(seed: int, defender_ids: tuple[str, ...]) -> tuple[dict[str, int], int]:

    seed_draws = random.Random(seed)
    
    sampling_seeds = {}
    
    for defender_id in defender_ids:
        sampling_seeds[defender_id] = seed_draws.randrange(2**31)
        
    return sampling_seeds, seed_draws.randrange(2**31)
