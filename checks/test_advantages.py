import numpy as np
import torch

from checks.scenario_helpers import TEST_SETTINGS, world_settings
from episodes.runner import EpisodeRunner
from learning.advantages import advantages_and_returns
from learning.experience import defender_decisions
from learning.networks import Critic
from learning.training_config import read_training_config
from policies.random_policy import RandomPolicy
from world.environment import WorldEnvironment
from world.environment_interface import EnvironmentInterface


def test_with_lambda_1_returns_are_the_discounted_rewards_to_the_end_whatever_the_critic_says():
    config = read_training_config(TEST_SETTINGS / "training_config.toml")
    gamma = config["advantages"]["gamma"]
    env = WorldEnvironment(world_settings())
    policies = {
        defender: RandomPolicy(len(env.action_choices(defender)), seed)
        for defender, seed in zip(env.get_defender_ids(), (3, 4), strict=True)
    }
    log = EpisodeRunner(EnvironmentInterface(env), policies).run()
    rewards = log.shared_rewards

    for defender in env.get_defender_ids():
        decisions = defender_decisions(log, defender)
        assert max(np.diff(decisions.intervals)) > 1
        critic = Critic(decisions.observations.shape[1], config["networks"]["hidden_sizes"])
        with torch.no_grad():
            values = critic(torch.tensor(decisions.observations)).numpy()

        _, returns = advantages_and_returns(rewards, decisions.intervals, values, gamma, 1.0)

        expected = [sum(gamma ** (u - t) * rewards[u] for u in range(t, len(rewards)))
                    for t in decisions.intervals]
        np.testing.assert_allclose(returns, expected, rtol=1e-5)


def test_a_worked_example_with_a_two_interval_decision():
    advantages, returns = advantages_and_returns(
        [-1.0, -2.0, -3.0, -4.0], np.array([0, 2, 3]), np.array([-5.0, -4.0, -2.0]), 0.5, 0.5
    )
    np.testing.assert_allclose(advantages, [1.9375, -0.5, -2.0])
    np.testing.assert_allclose(returns, [-3.0625, -4.5, -4.0])
