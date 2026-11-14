import random
from copy import deepcopy
from dataclasses import asdict, fields

import numpy as np
import pytest

from checks.scenario_helpers import OTHER_ZONE_NAMES, world_settings
from episodes.runner import EpisodeLog, EpisodeRunner
from policies.always_wait import AlwaysWait
from world.environment import WorldEnvironment
from world.environment_interface import EnvironmentInterface


def run(env, policies):
    return EpisodeRunner(EnvironmentInterface(env), policies).run()


def plain(log):
    data = asdict(log)
    data["observations"] = [{d: v.tolist() for d, v in row.items()} for row in data["observations"]]
    data["final_observations"] = {d: v.tolist() for d, v in data["final_observations"].items()}
    return data


def test_log_fields_are_fixed_and_separate_defender_data_from_hidden_truth():
    assert [field.name for field in fields(EpisodeLog)] == [
        "observations", "action_ids", "shared_rewards", "total_episode_reward",
        "final_observations", "observation_facts", "final_observation_facts", "world_reports", "script",
    ]


def test_wait_episode_records_all_intervals_rewards_and_final_observations():
    env = WorldEnvironment(world_settings())
    log = run(env, {"A": AlwaysWait(), "B": AlwaysWait()})
    assert env.state.elapsed_steps == 50
    for name in ("observations", "action_ids", "shared_rewards", "world_reports"):
        assert len(getattr(log, name)) == 50
    assert sum(log.shared_rewards) == -198
    assert type(log.total_episode_reward) is float
    assert log.total_episode_reward == -198.0
    for t in range(50):
        assert log.action_ids[t] == {"A": 0, "B": 0}
        assert log.shared_rewards[t] == (-2 if t == 0 else -4)
        report = log.world_reports[t]
        assert report["elapsed_steps"] == t + 1
        assert report["episode_finished"] is (t == 49)
        assert report["reward"]["shared_reward"] == log.shared_rewards[t]
        for defender in ("A", "B"):
            assert log.observations[t][defender].shape == (59,)
            assert log.observations[t][defender][0] == pytest.approx(t / 50)
    for defender in ("A", "B"):
        assert log.final_observations[defender][0] == pytest.approx(1)
        np.testing.assert_array_equal(log.final_observations[defender], env.encode_observation(defender))


def test_both_busy_intervals_have_no_policy_calls_or_fake_waits():
    env = WorldEnvironment(world_settings())
    calls = {"A": [], "B": []}

    def make_policy(defender):
        def policy(observation):
            calls[defender].append(float(observation[0]))
            return 3 if len(calls[defender]) == 1 else 0
        return policy

    log = run(env, {d: make_policy(d) for d in calls})
    assert log.action_ids[0] == {"A": 3, "B": 3}
    assert log.action_ids[1:4] == [{"A": None, "B": None}] * 3
    assert log.action_ids[4] == {"A": 0, "B": 0}
    assert log.shared_rewards[:4] == [-6, -6, -6, -4]
    assert log.total_episode_reward == sum(log.shared_rewards) == -6 * 3 - 4 * 47
    assert all(len(times) == 47 for times in calls.values())
    assert calls["A"][1] == pytest.approx(4 / 50)


def test_policy_receives_only_own_detached_vector_and_log_does_not_alias():
    env = WorldEnvironment(world_settings())
    expected_a = env.encode_observation("A")
    expected_b = env.encode_observation("B")
    inputs = {"A": [], "B": []}

    def make_policy(defender):
        def policy(observation):
            assert isinstance(observation, np.ndarray) and observation.dtype == np.float32
            assert observation.shape == (59,)
            inputs[defender].append(observation)
            if defender == "A":
                observation[:] = 999
            return 0
        return policy

    log = run(env, {d: make_policy(d) for d in inputs})
    np.testing.assert_array_equal(log.observations[0]["A"], expected_a)
    np.testing.assert_array_equal(inputs["B"][0], expected_b)
    assert inputs["A"][0] is not log.observations[0]["A"]
    log.observations[1]["A"][:] = 888
    assert not np.any(log.observations[0]["A"] == 888)
    assert not np.any(log.observations[2]["A"] == 888)
    before = deepcopy(env.state)
    log.final_observations["B"][:] = 777
    log.world_reports[0]["reward"]["shared_reward"] = 777
    log.world_reports[-1]["request_results"].clear()
    assert env.state == before
    assert not np.any(env.encode_observation("B") == 777)


@pytest.mark.parametrize("horizon,inspect", [(1, 2), (2, 2), (7, 3)])
@pytest.mark.parametrize("seed", [7, 31])
def test_choices_log_and_final_state_match_direct_execution(tmp_path, horizon, inspect, seed):
    settings = world_settings({**OTHER_ZONE_NAMES, "world.episode.max_steps": horizon,
                               "actions.duration_steps.inspect": inspect})
    env, direct = WorldEnvironment(settings), WorldEnvironment(settings)
    policies = {}
    for i, defender in enumerate(env.get_defender_ids()):
        rng = random.Random(seed + i)
        count = len(env.action_choices(defender))
        policies[defender] = lambda observation, rng=rng, count=count: rng.randrange(count)
    log = run(env, policies)
    assert len(log.shared_rewards) == len(log.world_reports) == horizon
    direct_total = 0.0
    for t, action_ids in enumerate(log.action_ids):
        commands = {}
        for defender, action in action_ids.items():
            np.testing.assert_array_equal(log.observations[t][defender], direct.encode_observation(defender))
            assert (action is None) == (direct.state.defenders[defender].job is not None)
            if action is not None:
                commands[defender] = direct.decode_action(defender, action)
        report = direct.step(commands)
        assert log.shared_rewards[t] == report["reward"]["shared_reward"]
        assert log.world_reports[t] == report
        assert report["episode_finished"] is (t == horizon - 1)
        direct_total += report["reward"]["shared_reward"]
    assert log.total_episode_reward == direct_total
    for defender in direct.get_defender_ids():
        np.testing.assert_array_equal(log.final_observations[defender], direct.encode_observation(defender))
    assert env.state == direct.state


def test_reset_horizon_and_unfinished_job_are_not_extra_decisions(tmp_path):
    env = WorldEnvironment(world_settings({"world.episode.max_steps": 1}))
    env.step({"A": ("wait", None), "B": ("wait", None)})
    calls = []

    def inspect(observation):
        calls.append(observation[0])
        return 1

    runner = EpisodeRunner(EnvironmentInterface(env), {"A": inspect, "B": AlwaysWait()})
    for _ in range(2):
        log = runner.run()
        assert len(log.shared_rewards) == 1 and env.state.elapsed_steps == 1
        assert env.state.defenders["A"].job.remaining_steps == 1
        assert log.world_reports[0]["episode_finished"]
    assert calls == [0, 0]


def test_each_run_returns_a_new_independent_log():
    env = WorldEnvironment(world_settings())
    runner = EpisodeRunner(EnvironmentInterface(env), {"A": AlwaysWait(), "B": AlwaysWait()})
    first = runner.run()
    saved = deepcopy(first)
    second = runner.run()
    assert first is not second
    assert first.observations is not second.observations
    assert first.world_reports is not second.world_reports
    assert plain(first) == plain(saved) == plain(second)
    second.shared_rewards.clear()
    second.world_reports[0]["elapsed_steps"] = 999
    second.observations[0]["A"][:] = 555
    assert plain(first) == plain(saved)


@pytest.mark.parametrize("policies,error", [
    ([], TypeError), ({"A": 0, "B": AlwaysWait()}, TypeError),
    ({}, ValueError), ({"A": AlwaysWait()}, ValueError),
    ({"A": AlwaysWait(), "B": AlwaysWait(), "C": AlwaysWait()}, ValueError),
])
def test_bad_policy_setup_never_advances_an_interval(policies, error):
    env = WorldEnvironment(world_settings())
    with pytest.raises(error):
        EpisodeRunner(EnvironmentInterface(env), policies).run()
    assert env.state.elapsed_steps == 0


@pytest.mark.parametrize("policies", [[], {"A": 0, "B": AlwaysWait()}])
def test_wrong_policy_types_fail_when_the_runner_is_created(policies):
    with pytest.raises(TypeError):
        EpisodeRunner(EnvironmentInterface(WorldEnvironment(world_settings())), policies)


@pytest.mark.parametrize("action", [-1, 13, True, np.int64(0)])
def test_bad_policy_output_is_rejected_before_world_progress(action):
    env = WorldEnvironment(world_settings())
    before = deepcopy(env.state)
    with pytest.raises((TypeError, ValueError)):
        run(env, {"A": lambda observation: action, "B": AlwaysWait()})
    assert env.state == before
