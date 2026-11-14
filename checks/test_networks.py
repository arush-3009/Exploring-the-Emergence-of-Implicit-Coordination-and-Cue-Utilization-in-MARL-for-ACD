from itertools import pairwise

import numpy as np
import pytest
import torch

from checks.scenario_helpers import world_settings
from learning.networks import Actor, Critic
from world.environment import WorldEnvironment


@pytest.mark.parametrize("observation_size,action_count,hidden_sizes", [
    (59, 13, (64, 64)), (59, 13, ()), (67, 17, [32]),
])
def test_actor_layers_follow_the_given_sizes(observation_size, action_count, hidden_sizes):
    actor = Actor(observation_size, action_count, hidden_sizes)
    linear = [layer for layer in actor.layers if isinstance(layer, torch.nn.Linear)]
    sizes = [observation_size, *hidden_sizes, action_count]
    assert [(layer.in_features, layer.out_features) for layer in linear] == list(pairwise(sizes))
    assert actor(torch.zeros(observation_size)).shape == (action_count,)
    assert actor(torch.zeros(5, observation_size)).shape == (5, action_count)


def test_an_untrained_actor_scores_every_action_almost_equally():
    env = WorldEnvironment(world_settings())
    for defender in env.get_defender_ids():
        actor = Actor(len(env.encode_observation(defender)), len(env.action_choices(defender)), (64, 64))
        observations = torch.tensor(np.stack([env.encode_observation(defender), np.ones(59, dtype=np.float32)]))
        with torch.no_grad():
            probabilities = torch.softmax(actor(observations), dim=1)
        assert torch.allclose(probabilities, torch.full_like(probabilities, 1 / 13), atol=0.002)


def test_the_critic_gives_one_value_per_observation():
    critic = Critic(59, (64, 64))
    assert critic(torch.zeros(59)).shape == ()
    # shape (5,), a (5, 1) column would broadcast to 5 x 5
    assert critic(torch.zeros(5, 59)).shape == (5,)
