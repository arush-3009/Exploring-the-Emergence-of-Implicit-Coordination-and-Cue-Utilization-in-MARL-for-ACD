import numpy as np

from checks.scenario_helpers import world_settings
from episodes.runner import EpisodeRunner
from learning.experience import defender_decisions
from policies.random_policy import RandomPolicy
from world.environment import WorldEnvironment
from world.environment_interface import EnvironmentInterface


class Recording:

    def __init__(self, policy):
        self.policy = policy
        self.seen = []
        self.chosen = []

    def __call__(self, observation):
        action = self.policy(observation)
        self.seen.append(observation)
        self.chosen.append(action)
        return action


def test_decisions_are_exactly_the_policy_calls_and_skip_busy_intervals():
    env = WorldEnvironment(world_settings())
    policies = {
        defender: Recording(RandomPolicy(len(env.action_choices(defender)), seed))
        for defender, seed in zip(env.get_defender_ids(), (3, 4), strict=True)
    }
    log = EpisodeRunner(EnvironmentInterface(env), policies).run()

    for defender, recording in policies.items():
        decisions = defender_decisions(log, defender)
        np.testing.assert_array_equal(decisions.observations, np.stack(recording.seen))
        assert decisions.action_ids.tolist() == recording.chosen
        assert len(decisions.intervals) < len(log.shared_rewards)
