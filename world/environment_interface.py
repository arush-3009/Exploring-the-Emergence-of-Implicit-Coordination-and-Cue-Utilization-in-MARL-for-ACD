from dataclasses import asdict

from world.environment import WorldEnvironment
from world.results import BoundaryResult, WorldStepReport


class EnvironmentInterface:

    def __init__(self, environment: WorldEnvironment) -> None:
        self._environment = environment


    def reset(self) -> BoundaryResult:
        self._environment.reset()
        return self._result(report=None)


    # Require exactly one choice per free defender and advance one interval.
    def step(self, defender_action_ids: dict[str, int]) -> BoundaryResult:
        
        if self._environment.is_episode_finished():
            raise RuntimeError("Episode finished; call reset() before another step")
        if not isinstance(defender_action_ids, dict):
            raise TypeError("defender_action_ids must be a dictionary")

    
        defender_commands = {
            defender_id: self._environment.decode_action(defender_id, action_id)
            for defender_id, action_id in defender_action_ids.items()
        }
        
        required = self._defenders_to_act()
        
        #raise error if a free defender hasn't been assigned a command.
        missing = [defender_id for defender_id in required if defender_id not in defender_commands]
        if missing:
            raise ValueError(f"Missing choices for free defenders: {missing}")
        
        #raise error if a busy defender is being assigned a command.
        busy = [defender_id for defender_id in defender_commands if defender_id not in required]
        if busy:
            raise ValueError(f"Omit busy defenders; their jobs continue: {busy}")


        #Run environment state/interval transition step.
        report = self._environment.step(defender_commands)
        
        
        return self._result(report)



    def _defenders_to_act(self) -> tuple[str, ...]:
        
        if self._environment.is_episode_finished():
            return ()
        
        ret = []
        for defender_id in self._environment.get_defender_ids():
            if self._environment.is_defender_free(defender_id):
                ret.append(defender_id)
        
        return tuple(ret)


    def _result(self, report: WorldStepReport | None) -> BoundaryResult:
        
        observation_facts = {}
        observations = {}
        for defender_id in self._environment.get_defender_ids():
            observation_facts[defender_id] = self._environment.observe(defender_id)
            observations[defender_id] = self._environment.encode(defender_id, observation_facts[defender_id])

        return {
            
            "observations": observations,

            "observation_facts": observation_facts,
            
            "defenders_to_act": self._defenders_to_act(),
            
            "shared_reward": None if report is None else report["reward"]["shared_reward"],
            
            "episode_finished": self._environment.is_episode_finished(),
            
            "world_report": report,

            "script": asdict(self._environment.state.script),
        }
