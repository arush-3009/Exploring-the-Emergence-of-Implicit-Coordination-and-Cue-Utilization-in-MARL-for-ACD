import copy

import numpy as np
import pytest
import torch
from torch.distributions import Categorical

from learning.networks import Actor, Critic
from learning.ppo import PPOLearner


def one_observation_batch():
    observations = np.tile(np.linspace(0, 1, 59, dtype=np.float32), (40, 1))
    action_ids = np.array([3] * 20 + [7] * 20)
    advantages = np.array([1.0] * 20 + [-1.0] * 20)
    returns = np.full(40, -50.0)
    return observations, action_ids, advantages, returns


def settings(**changes):
    return {"actor_learning_rate": 3e-4, "critic_learning_rate": 1e-3, "clip_epsilon": 0.2,
            "epochs": 4, "minibatch_size": 64, "entropy_coefficient": 0.0} | changes


def probabilities(actor, observation):
    with torch.no_grad():
        return torch.softmax(actor(torch.tensor(observation)), dim=0)


def test_an_update_follows_the_advantages_and_moves_the_critic_towards_the_returns():
    torch.manual_seed(0)
    actor, critic = Actor(59, 13, (64, 64)), Critic(59, (64, 64))
    observations, action_ids, advantages, returns = one_observation_batch()
    before = probabilities(actor, observations[0])
    with torch.no_grad():
        value_before = critic(torch.tensor(observations[0])).item()

    PPOLearner(actor, critic, settings(), seed=0).update(observations, action_ids, advantages, returns)

    after = probabilities(actor, observations[0])
    assert after[3] > before[3] and after[7] < before[7]
    with torch.no_grad():
        value_after = critic(torch.tensor(observations[0])).item()
    assert abs(value_after - -50) < abs(value_before - -50)


def test_the_clip_limits_how_far_one_batch_moves_a_probability():
    ratios = {}
    for clip in (0.2, 1e6):
        torch.manual_seed(0)
        actor, critic = Actor(59, 13, (64, 64)), Critic(59, (64, 64))
        observations, action_ids, advantages, returns = one_observation_batch()
        before = probabilities(actor, observations[0])[3]
        learner = PPOLearner(actor, critic, settings(clip_epsilon=clip, epochs=50), seed=0)
        learner.update(observations, action_ids, advantages, returns)
        ratios[clip] = (probabilities(actor, observations[0])[3] / before).item()
    assert ratios[0.2] < 1.5
    assert ratios[1e6] > 2


def test_the_entropy_bonus_alone_spreads_the_probabilities_out():
    observations = np.tile(np.linspace(0, 1, 59, dtype=np.float32), (40, 1))
    batch = (observations, np.full(40, 3), np.full(40, 5.0), np.full(40, -50.0))
    for coefficient in (0.0, 0.01):
        torch.manual_seed(0)
        actor, critic = Actor(59, 13, (64, 64)), Critic(59, (64, 64))
        with torch.no_grad():
            actor.layers[-1].bias[3] = 3.0
        weights_before = [weights.clone() for weights in actor.parameters()]
        before = Categorical(probs=probabilities(actor, observations[0])).entropy()

        learner = PPOLearner(actor, critic, settings(entropy_coefficient=coefficient), seed=0)
        statistics = learner.update(*batch)

        after = Categorical(probs=probabilities(actor, observations[0])).entropy()
        if coefficient == 0:
            assert all(torch.equal(old, new) for old, new in zip(weights_before, actor.parameters()))
        else:
            assert after > before
        assert statistics["actor_loss"] == pytest.approx(-coefficient * statistics["entropy"])


def test_the_same_seed_gives_the_same_weights_whatever_else_draws_random_numbers():
    torch.manual_seed(0)
    actor, critic = Actor(59, 13, (64, 64)), Critic(59, (64, 64))
    rng = np.random.default_rng(0)
    batch = (rng.random((200, 59), dtype=np.float32), rng.integers(0, 13, 200),
             rng.normal(size=200), rng.normal(size=200))

    weights = []
    for seed in (5, 5, 6):
        learner = PPOLearner(copy.deepcopy(actor), copy.deepcopy(critic), settings(), seed)
        torch.rand(10)
        learner.update(*batch)
        weights.append(torch.cat([p.flatten() for p in learner.actor.parameters()]))
    assert torch.equal(weights[0], weights[1])
    assert not torch.equal(weights[0], weights[2])
