import json

import numpy as np

from checks.scenario_helpers import world_settings
from episodes.runner import EpisodeRunner
from policies.always_wait import AlwaysWait
from world.environment import WorldEnvironment
from world.environment_interface import EnvironmentInterface


def test_wait_is_action_id_zero_for_every_defender():
    env = WorldEnvironment(world_settings())
    for defender in env.get_defender_ids():
        assert env.action_choices(defender)[0] == ("wait", None)
        assert env.decode_action(defender, AlwaysWait()(env.encode_observation(defender))) == ("wait", None)


def test_always_returns_wait_and_ignores_and_preserves_the_observation():
    policy = AlwaysWait()
    observation = np.arange(59, dtype=np.float32)
    original = observation.copy()
    observation.flags.writeable = False
    choices = [policy(observation) for _ in range(20)] + [policy(np.full(59, -1.0)) for _ in range(20)]
    assert choices == [0] * 40
    assert all(type(choice) is int for choice in choices)
    np.testing.assert_array_equal(observation, original)


def test_describe_is_a_saveable_dict():
    assert json.loads(json.dumps(AlwaysWait().describe())) == {"type": "AlwaysWait"}


def test_always_wait_episode_is_the_do_nothing_baseline():
    log = EpisodeRunner(EnvironmentInterface(WorldEnvironment(world_settings())), {"A": AlwaysWait(), "B": AlwaysWait()}).run()
    assert all(action_ids == {"A": 0, "B": 0} for action_ids in log.action_ids)
    assert log.total_episode_reward == -198.0
    assert sum(report["reward"]["compromised_server_count"] for report in log.world_reports) == 99
    assert sum(report["reward"]["failed_request_count"] for report in log.world_reports) == 0
