import random
from copy import deepcopy

import numpy as np
import pytest

from checks.scenario_helpers import OTHER_ZONE_NAMES, world_settings
from world.environment import WorldEnvironment
from world.environment_interface import EnvironmentInterface

KEYS = {"observations", "observation_facts", "defenders_to_act", "shared_reward", "episode_finished", "world_report", "script"}


def check_result(result, env, required, reward, finished=False):
    assert set(result) == KEYS
    assert result["defenders_to_act"] == required
    assert result["shared_reward"] == reward
    assert result["episode_finished"] is finished
    assert tuple(result["observations"]) == env.get_defender_ids()
    for defender_id, vector in result["observations"].items():
        assert vector.dtype == np.float32 and vector.shape == (59,)
        np.testing.assert_array_equal(vector, env.encode_observation(defender_id))
    report = result["world_report"]
    if reward is None:
        assert report is None
    else:
        assert report["reward"]["shared_reward"] == reward
        assert report["elapsed_steps"] == env.state.elapsed_steps
        assert report["episode_finished"] is finished


def test_reset_returns_initial_observations_without_inventing_reward():
    env = WorldEnvironment(world_settings())
    interface = EnvironmentInterface(env)
    initial = deepcopy(env.state)
    result = interface.reset()
    check_result(result, env, ("A", "B"), None)
    assert env.state == initial
    assert env.get_defender_ids() == ("A", "B") and not env.is_episode_finished()
    assert env.state.elapsed_steps == 0


def test_inspect_acceptance_then_omitted_busy_completion_and_reward():
    env = WorldEnvironment(world_settings())
    interface = EnvironmentInterface(env)
    first = interface.step({"A": 1, "B": 0})
    check_result(first, env, ("B",), -2.0)
    assert env.state.elapsed_steps == 1
    assert env.observe("A")["last_command_feedback"] == 2
    assert env.observe("A")["job_remaining_steps"] == 1
    second = interface.step({"B": 0})
    check_result(second, env, ("A", "B"), -4.0)
    assert env.state.elapsed_steps == 2
    assert env.observe("A")["last_command_feedback"] == 1
    assert env.observe("A")["servers"]["A1"]["inspection_finding"] == 1


def test_both_busy_empty_choices_still_advance_and_score_every_interval():
    env = WorldEnvironment(world_settings())
    interface = EnvironmentInterface(env)
    result = interface.step({"A": 3, "B": 3})
    for boundary in range(1, 5):
        if boundary > 1:
            result = interface.step({})
        assert env.state.elapsed_steps == boundary
        check_result(result, env, () if boundary < 4 else ("A", "B"),
                     -6.0 if boundary < 4 else -4.0)
        if boundary in (2, 3):
            assert env.observe("A")["last_command_feedback"] == 0
    assert env.state.hosts["A1"].isolated and not env.state.hosts["A1"].compromised


@pytest.mark.parametrize("choices,error", [
    (None, TypeError), ([], TypeError), ({}, ValueError),
    ({"A": 0}, ValueError), ({"A": 0, "B": 0, "C": 0}, ValueError),
    ({1: 0, "B": 0}, TypeError), ({"A": 0, "B": -1}, ValueError),
    ({"A": 0, "B": 13}, ValueError), ({"A": 0, "B": True}, TypeError),
    ({"A": 0, "B": 1.0}, TypeError), ({"A": 0, "B": "0"}, TypeError),
    ({"A": 0, "B": np.int64(0)}, TypeError),
])
def test_bad_batch_fails_before_any_world_mutation(choices, error):
    env = WorldEnvironment(world_settings())
    before = deepcopy(env.state)
    with pytest.raises(error):
        EnvironmentInterface(env).step(choices)
    assert env.state == before


def test_busy_choice_raises_without_progress_then_correct_batch_continues():
    env = WorldEnvironment(world_settings())
    interface = EnvironmentInterface(env)
    interface.step({"A": 3, "B": 0})
    before = deepcopy(env.state)
    with pytest.raises(ValueError, match="Omit busy defenders"):
        interface.step({"A": 0, "B": 0})
    assert env.state == before
    interface.step({"B": 0})
    assert env.state.defenders["A"].job.remaining_steps == 2
    report = env.step({"A": ("wait", None), "B": ("wait", None)})
    assert report["defender_command_results"]["A"] == "rejected"


def test_returned_storage_is_detached_and_old_results_do_not_change():
    env = WorldEnvironment(world_settings())
    interface = EnvironmentInterface(env)
    result = interface.reset()
    saved = deepcopy(result)
    interface.step({"A": 1, "B": 0})
    np.testing.assert_array_equal(result["observations"]["A"], saved["observations"]["A"])
    assert result["defenders_to_act"] == ("A", "B")
    result["observations"]["A"][:] = 999
    result["defenders_to_act"] = ()
    assert not np.any(env.encode_observation("A") == 999)
    check_result(interface.step({"B": 0}), env, ("A", "B"), -4.0)


def test_world_report_is_the_step_report_and_editing_it_changes_nothing():
    env, control = WorldEnvironment(world_settings()), WorldEnvironment(world_settings())
    interface = EnvironmentInterface(env)
    assert interface.reset()["world_report"] is None
    result = interface.step({"A": 2, "B": 0})
    expected = control.step({"A": ("isolate", "A1"), "B": ("wait", None)})
    report = result["world_report"]
    assert report == expected
    assert report["defender_completions"] == {"A": "isolate"}
    assert report["attacks_started"] == {"A1": "B1"}
    assert report["reward"]["failed_request_count"] == 3
    report["reward"]["shared_reward"] = 999
    report["request_results"][0]["succeeded"] = False
    report["request_results"].clear()
    report["defender_completions"].clear()
    report["attacks_started"].clear()
    report["elapsed_steps"] = 999
    assert env.state == control.state
    later = interface.step({"A": 0, "B": 0})
    assert later["world_report"] == control.step({"A": ("wait", None), "B": ("wait", None)})
    assert later["world_report"]["attack_completions"] == {"A1": "failed"}
    assert later["world_report"] is not report


def test_wrapper_can_resume_existing_environment_without_cached_state():
    env = WorldEnvironment(world_settings())
    env.step({"A": ("inspect", "A2"), "B": ("wait", None)})
    result = EnvironmentInterface(env).step({"B": 0})
    check_result(result, env, ("A", "B"), -4.0)
    assert env.state.elapsed_steps == 2


def test_private_change_is_not_added_to_teammate_vector():
    env = WorldEnvironment(world_settings())
    interface = EnvironmentInterface(env)
    original = interface.reset()["observations"]["B"]
    env.state.hosts["A3"].compromised = True
    env.state.hosts["B3"].compromised = True
    result = interface._result(report=None)
    np.testing.assert_array_equal(result["observations"]["B"], original)
    assert set(result) == KEYS
    assert result["shared_reward"] is None
    assert result["world_report"] is None


def test_terminal_keeps_final_observation_reward_and_unfinished_jobs(tmp_path):
    env = WorldEnvironment(world_settings({"world.episode.max_steps": 1}))
    interface = EnvironmentInterface(env)
    result = interface.step({"A": 1, "B": 0})
    check_result(result, env, (), -2.0, True)
    assert result["observations"]["A"][0] == 1
    assert env.state.defenders["A"].job.remaining_steps == 1
    before = deepcopy(env.state)
    with pytest.raises(RuntimeError, match="Episode finished"):
        interface.step({})
    assert env.state == before
    check_result(interface.reset(), env, ("A", "B"), None)
    assert env.state.elapsed_steps == 0 and env.state.defenders["A"].job is None


@pytest.mark.parametrize("alternate", [False, True])
@pytest.mark.parametrize("seed", [7, 31, 82])
def test_whole_episode_matches_direct_world_calls(seed, alternate, tmp_path):
    overrides = {}
    if alternate:
        overrides = {**OTHER_ZONE_NAMES, "world.episode.max_steps": 7, "actions.duration_steps.inspect": 3,
                     "actions.duration_steps.restore": 5, "actions.duration_steps.isolate": 2}
    env, direct = WorldEnvironment(world_settings(overrides)), WorldEnvironment(world_settings(overrides))
    interface = EnvironmentInterface(env)
    result = interface.reset()
    rng = random.Random(seed)
    while not result["episode_finished"]:
        choices = {defender: rng.randrange(len(env.action_choices(defender)))
                   for defender in result["defenders_to_act"]}
        commands = {defender: direct.decode_action(defender, choice)
                    for defender, choice in choices.items()}
        report = direct.step(commands)
        result = interface.step(choices)
        assert env.state == direct.state
        assert result["world_report"] == report
        expected_free = tuple(d for d in direct.get_defender_ids()
                              if direct.state.defenders[d].job is None) if not report["episode_finished"] else ()
        check_result(result, direct, expected_free, report["reward"]["shared_reward"], report["episode_finished"])
    check_result(interface.reset(), env, env.get_defender_ids(), None)
