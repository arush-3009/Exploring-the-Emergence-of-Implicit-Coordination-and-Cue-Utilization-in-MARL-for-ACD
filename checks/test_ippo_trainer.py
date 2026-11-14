import random

import numpy as np
import pytest
import torch

from checks.scenario_helpers import (
    OTHER_ZONE_NAMES,
    RANDOM_INTRUSION,
    TEST_SETTINGS,
    world_settings,
)
from episodes.runner import EpisodeRunner
from learning.experience import defender_decisions
from learning.ippo_trainer import IPPOTrainer, get_defender_decisions_batch
from learning.networks import Critic
from learning.training_config import read_training_config
from policies.random_policy import RandomPolicy
from world.environment import WorldEnvironment
from world.environment_interface import EnvironmentInterface


def small_config():
    config = read_training_config(TEST_SETTINGS / "training_config.toml")
    config["training"]["episodes_per_iteration"] = 2
    config["ppo"]["epochs"] = 2
    return config


def all_weights(trainer):
    return torch.cat([weights.flatten() for learner in trainer.learners.values()
                      for weights in [*learner.actor.parameters(), *learner.critic.parameters()]])


def test_a_batch_computes_advantages_within_each_episode_before_joining_them():
    env = WorldEnvironment(world_settings())
    policies = {defender: RandomPolicy(len(env.action_choices(defender)), seed)
                for defender, seed in zip(env.get_defender_ids(), (3, 4), strict=True)}
    runner = EpisodeRunner(EnvironmentInterface(env), policies)
    logs = [runner.run() for _ in range(3)]
    critic = Critic(len(env.encode_observation("B")), (64, 64))

    batch = get_defender_decisions_batch(logs, "B", critic, gamma=0.99, gae_lambda=1.0)

    expected = []
    for log in logs:
        rewards = log.shared_rewards
        for t in defender_decisions(log, "B").intervals:
            expected.append(sum(0.99 ** (u - t) * rewards[u] for u in range(t, len(rewards))))
    np.testing.assert_allclose(batch["returns"], expected, rtol=1e-5)
    assert {len(values) for values in batch.values()} == {len(expected)}


def test_an_iteration_updates_every_defender_and_its_policy_plays_the_updated_actor():
    trainer = IPPOTrainer(WorldEnvironment(world_settings()), small_config(), seed=0)
    before = {defender: [weights.clone() for weights in learner.actor.parameters()]
              for defender, learner in trainer.learners.items()}
    assert not torch.equal(before["A"][0], before["B"][0])

    logs, stats = trainer.run_iteration()

    assert len(logs) == 2 and set(stats) == set(trainer.learners)
    for defender, learner in trainer.learners.items():
        assert trainer.policies[defender].actor is learner.actor
        assert any(not torch.equal(old, new) for old, new in zip(before[defender], learner.actor.parameters()))


def test_the_same_seed_repeats_a_run_exactly_whatever_else_draws_random_numbers():
    def run(seed):
        trainer = IPPOTrainer(WorldEnvironment(world_settings()), small_config(), seed)
        rewards = []
        for _ in range(2):
            torch.rand(5)
            rewards += [log.total_episode_reward for log in trainer.run_iteration()[0]]
        return rewards, all_weights(trainer)

    first, again, other = run(5), run(5), run(6)
    assert first[0] == again[0] and torch.equal(first[1], again[1])
    assert not torch.equal(first[1], other[1])


def test_defenders_and_sizes_come_from_the_environment(tmp_path):
    env = WorldEnvironment(world_settings({**OTHER_ZONE_NAMES, "world.episode.max_steps": 7}))

    logs, stats = IPPOTrainer(env, small_config(), seed=0).run_iteration()

    assert set(stats) == {"X", "Y"}
    assert all(len(log.shared_rewards) == 7 for log in logs)


def test_the_world_seed_is_drawn_after_every_defender_seed(tmp_path):
    env = WorldEnvironment(world_settings(RANDOM_INTRUSION))
    trainer = IPPOTrainer(env, small_config(), seed=0)
    draws = random.Random(0)
    expected = [draws.randrange(2**31) for _ in range(7)]

    assert [seed for seeds in trainer.defender_seeds.values() for seed in seeds.values()] == expected[:6]
    assert env.world_seed == expected[6]


def test_training_that_diverges_stops_with_a_clear_error():
    trainer = IPPOTrainer(WorldEnvironment(world_settings()), small_config(), seed=0)
    learner = trainer.learners["B"]
    real_update = learner.update

    def update_then_diverge(**batch):
        stats = real_update(**batch)
        with torch.no_grad():
            learner.critic.layers[0].weight[0, 0] = float("nan")
        return stats

    learner.update = update_then_diverge
    with pytest.raises(FloatingPointError, match="B's Critic weights are no longer finite after iteration 1"):
        trainer.run_iteration()
