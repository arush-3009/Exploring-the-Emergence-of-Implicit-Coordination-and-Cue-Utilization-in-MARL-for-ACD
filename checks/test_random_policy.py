import json
import random
from copy import deepcopy
from dataclasses import asdict

import numpy as np
import pytest

from checks.scenario_helpers import OTHER_ZONE_NAMES, world_settings
from episodes.runner import EpisodeRunner
from policies.random_policy import RandomPolicy
from world.environment import WorldEnvironment
from world.environment_interface import EnvironmentInterface


def episode_json(log):
    return json.dumps(asdict(log), sort_keys=True, default=lambda value: value.tolist())


@pytest.mark.parametrize("count,seed,error", [
    (True, 1, TypeError), (1.0, 1, TypeError), (None, 1, TypeError),
    (0, 1, ValueError), (-1, 1, ValueError),
    (13, True, TypeError), (13, 1.0, TypeError), (13, None, TypeError),
    (13, "1", TypeError), (np.int64(13), 1, TypeError),
])
def test_rejects_invalid_construction(count, seed, error):
    with pytest.raises(error):
        RandomPolicy(count, seed)


def test_recreated_seed_repeats_and_policy_does_not_use_or_change_observation():
    first = RandomPolicy(13, 101)
    replay = RandomPolicy(13, 101)
    observation = np.arange(59, dtype=np.float32)
    original = observation.copy()
    observation.flags.writeable = False
    choices = [first(observation) for _ in range(256)]
    assert choices == [replay(np.full(59, -999, dtype=np.float32)) for _ in range(256)]
    assert all(type(choice) is int and 0 <= choice < 13 for choice in choices)
    assert set(choices) == set(range(13))
    np.testing.assert_array_equal(observation, original)


def test_single_choice_and_integer_seeds():
    for seed in (0, -7, 2**100):
        policy = RandomPolicy(1, seed)
        assert [policy(np.zeros(1)) for _ in range(10)] == [0] * 10


def test_other_defender_and_global_random_calls_cannot_consume_this_sequence():
    global_state = random.getstate()
    try:
        first = RandomPolicy(13, 101)
        second = RandomPolicy(13, 202)
        replay_second = RandomPolicy(13, 202)
        actual = []
        for i in range(30):
            for _ in range(i):
                first(np.zeros(1))
                random.random()
            actual.append(second(np.zeros(1)))
        assert actual == [replay_second(np.zeros(1)) for _ in range(30)]
    finally:
        random.setstate(global_state)


def test_describe_is_saveable_unchanged_by_draws_and_enough_to_recreate_the_policy():
    policy = RandomPolicy(13, 101)
    description = json.loads(json.dumps(policy.describe()))
    assert description == {"type": "RandomPolicy", "seed": 101, "action_count": 13}
    first = [policy(np.zeros(1)) for _ in range(30)]
    assert policy.describe() == description
    rebuilt = RandomPolicy(description["action_count"], description["seed"])
    assert [rebuilt(np.zeros(1)) for _ in range(30)] == first


def test_policy_does_not_change_module_random_state():
    before = random.getstate()
    policy = RandomPolicy(13, 101)
    for _ in range(20):
        policy(np.zeros(1))
    assert random.getstate() == before


def test_environment_reset_does_not_rewind_policy():
    policy = RandomPolicy(13, 101)
    reference = RandomPolicy(13, 101)
    env = WorldEnvironment(world_settings())
    first = [policy(env.encode_observation("A")) for _ in range(15)]
    env.reset()
    second = [policy(env.encode_observation("A")) for _ in range(15)]
    assert first + second == [reference(np.zeros(1)) for _ in range(30)]


@pytest.mark.parametrize("horizon,inspect", [(50, 2), (1, 3), (7, 1)])
@pytest.mark.parametrize("seeds", [(101, 202), (303, 404)])
def test_whole_episode_replays_and_matches_world_execution(tmp_path, horizon, inspect, seeds):
    settings = world_settings({**OTHER_ZONE_NAMES, "world.episode.max_steps": horizon,
                               "actions.duration_steps.inspect": inspect})
    env = WorldEnvironment(settings)
    interface = EnvironmentInterface(env)

    def fresh_policies():
        return {defender: RandomPolicy(len(env.action_choices(defender)), seed)
                for defender, seed in zip(env.get_defender_ids(), seeds, strict=True)}

    run = EpisodeRunner(interface, fresh_policies()).run()
    final = deepcopy(env.state)
    replay = EpisodeRunner(interface, fresh_policies()).run()
    assert episode_json(run) == episode_json(replay)
    assert env.state == final
    assert len(run.shared_rewards) == horizon
    assert run.total_episode_reward == sum(run.shared_rewards)

    direct = WorldEnvironment(settings)
    expected_policies = fresh_policies()
    for t, action_ids in enumerate(run.action_ids):
        commands = {}
        for defender, action_id in action_ids.items():
            np.testing.assert_array_equal(run.observations[t][defender], direct.encode_observation(defender))
            assert (action_id is None) == (direct.state.defenders[defender].job is not None)
            if action_id is not None:
                assert action_id == expected_policies[defender](run.observations[t][defender])
                commands[defender] = direct.decode_action(defender, action_id)
        report = direct.step(commands)
        assert run.shared_rewards[t] == report["reward"]["shared_reward"]
        assert run.world_reports[t] == report
    for defender in direct.get_defender_ids():
        np.testing.assert_array_equal(run.final_observations[defender], direct.encode_observation(defender))
    assert direct.state == final
