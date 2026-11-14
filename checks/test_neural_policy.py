import copy
import math

import numpy as np
import pytest
import torch

from checks.scenario_helpers import OTHER_ZONE_NAMES, world_settings
from episodes.runner import EpisodeRunner
from learning.networks import Actor
from policies.neural_policy import NeuralPolicy
from world.environment import WorldEnvironment
from world.environment_interface import EnvironmentInterface


def neural_team(env, mode="sample", seeds=(13, 47)):
    team = {}
    for index, (defender, seed) in enumerate(zip(env.get_defender_ids(), seeds, strict=True)):
        torch.manual_seed(index)
        actor = Actor(len(env.encode_observation(defender)), len(env.action_choices(defender)), (64, 64))
        team[defender] = NeuralPolicy(actor, seed, mode)
    return team


def test_same_weights_and_seed_give_the_same_choices_and_the_observation_is_unchanged():
    env = WorldEnvironment(world_settings())
    actor = Actor(59, 13, (64, 64))
    first = NeuralPolicy(actor, 7, "sample")
    replay = NeuralPolicy(copy.deepcopy(actor), 7, "sample")
    other_seed = NeuralPolicy(actor, 8, "sample")
    observation = env.encode_observation("A")
    original = observation.copy()
    choices = [first(observation) for _ in range(300)]
    assert choices == [replay(observation) for _ in range(300)]
    assert choices != [other_seed(observation) for _ in range(300)]
    assert all(type(choice) is int and 0 <= choice < 13 for choice in choices)
    np.testing.assert_array_equal(observation, original)


def test_sampling_follows_the_actor_probabilities():
    actor = Actor(59, 13, (64, 64))
    with torch.no_grad():
        actor.layers[-1].bias[5] = math.log(0.9 * 12 / 0.1)  # about 90% for action 5
    policy = NeuralPolicy(actor, 3, "sample")
    choices = [policy(np.zeros(59, dtype=np.float32)) for _ in range(3000)]
    assert 0.87 < choices.count(5) / len(choices) < 0.93
    assert len(set(choices)) > 5


def test_greedy_takes_the_highest_score_whatever_the_seed():
    actor = Actor(59, 13, (64, 64))
    with torch.no_grad():
        actor.layers[-1].bias[9] = 1.0
    for seed in (0, 1, 2):
        policy = NeuralPolicy(actor, seed, "greedy")
        assert {policy(np.zeros(59, dtype=np.float32)) for _ in range(20)} == {9}


def test_calling_the_policy_never_changes_the_actor():
    env = WorldEnvironment(world_settings())
    actor = Actor(59, 13, (64, 64))
    before = copy.deepcopy(actor.state_dict())
    policy = NeuralPolicy(actor, 5, "sample")
    for _ in range(100):
        policy(env.encode_observation("B"))
    assert all(torch.equal(before[name], value) for name, value in actor.state_dict().items())
    assert all(parameter.grad is None for parameter in actor.parameters())


def test_an_unknown_mode_is_rejected():
    with pytest.raises(ValueError):
        NeuralPolicy(Actor(59, 13, (64,)), 0, "best")


def test_a_neural_team_plays_describes_itself_and_replays_exactly():
    env = WorldEnvironment(world_settings())
    policies = neural_team(env)
    log = EpisodeRunner(EnvironmentInterface(env), policies).run()
    assert len(log.shared_rewards) == 50
    assert all(action is None or 0 <= action < 13 for ids in log.action_ids for action in ids.values())

    assert policies["A"].describe() == {"type": "NeuralPolicy", "mode": "sample", "seed": 13,
                          "observation_size": 59, "action_count": 13, "hidden_sizes": [64, 64]}

    replay = EpisodeRunner(EnvironmentInterface(env), neural_team(env)).run()
    assert replay.action_ids == log.action_ids
    assert replay.shared_rewards == log.shared_rewards


def test_sizes_come_from_the_environment_under_other_world_settings(tmp_path):
    env = WorldEnvironment(world_settings({**OTHER_ZONE_NAMES, "world.episode.max_steps": 7,
                                           "actions.duration_steps.restore": 2}))
    for mode in ("sample", "greedy"):
        log = EpisodeRunner(EnvironmentInterface(env), neural_team(env, mode)).run()
        assert len(log.shared_rewards) == 7
        assert set(log.action_ids[0]) == {"X", "Y"}
