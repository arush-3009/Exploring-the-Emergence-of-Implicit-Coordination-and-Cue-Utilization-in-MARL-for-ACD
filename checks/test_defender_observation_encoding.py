import random
from copy import deepcopy

import numpy as np
import pytest

from checks.scenario_helpers import world_settings
from observations.defender_observation_encoding import (
    encode_defender_observation,
    observation_feature_names,
)
from world.environment import WorldEnvironment
from world.state import AttackJob, InspectionFinding, MonitoringWarning

WAIT = {"A": ("wait", None), "B": ("wait", None)}


def named_vector(env, defender_id):
    names = observation_feature_names(3)
    vector = env.encode_observation(defender_id)
    assert vector.shape == (59,)
    assert vector.dtype == np.float32
    assert np.isfinite(vector).all()
    return dict(zip(names, vector, strict=True))


@pytest.mark.parametrize("defender_id,extra", [("A", 1), ("B", 0)])
def test_exact_reset_vector_and_names(defender_id, extra):
    env = WorldEnvironment(world_settings())
    # the own status part
    expected_own = [0, extra, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0]
    # one server's part
    expected_server = [1, 0, 1, 0, 0, 1, 0, 0, 0, -1, 1, 0, 0, -1]
    np.testing.assert_array_equal(env.encode_observation(defender_id), expected_own + expected_server * 3)
    names = observation_feature_names(3)
    assert len(names) == len(set(names)) == 59
    assert names[:17] == (
        "elapsed_fraction", "extra_detector_available",
        "job_action.no_job", "job_action.inspect", "job_action.isolate", "job_action.restore", "job_action.reconnect",
        "job_target.none", "job_target.server_1", "job_target.server_2", "job_target.server_3",
        "job_remaining_fraction", "last_command_feedback.none", "last_command_feedback.completed",
        "last_command_feedback.accepted", "last_command_feedback.already_satisfied", "last_command_feedback.rejected",
    )
    named_vector(env, defender_id)


def test_busy_then_completed_inspection_and_scaled_historical_age():
    env = WorldEnvironment(world_settings())
    env.step({"A": ("inspect", "A2"), "B": ("wait", None)})
    own = named_vector(env, "A")
    assert own["elapsed_fraction"] == pytest.approx(1 / 50)
    assert own["job_action.inspect"] == own["job_target.server_2"] == 1
    assert own["job_remaining_fraction"] == 0.25  # 1 interval left of a longest job of 4
    assert own["last_command_feedback.accepted"] == 1
    env.step({"B": ("wait", None)})
    own = named_vector(env, "A")
    assert own["job_action.no_job"] == own["job_target.none"] == 1
    assert own["last_command_feedback.completed"] == 1
    assert own["server_2.inspection_finding.clean"] == 1
    assert own["server_2.inspection_age_fraction"] == 0
    assert own["server_1.warning_received"] == 1
    assert own["server_1.warning_age_fraction"] == 0
    env.step(WAIT)
    own = named_vector(env, "A")
    assert own["server_2.inspection_age_fraction"] == pytest.approx(1 / 50)
    assert own["server_1.warning_age_fraction"] == pytest.approx(1 / 50)


def test_private_warning_and_visible_peer_work_remain_separate():
    env = WorldEnvironment(world_settings())
    env.step(WAIT)
    env.step(WAIT)
    before = env.encode_observation("B")
    env.state.hosts["A3"].compromised = True
    env.state.hosts["B3"].compromised = True
    env.state.attack_jobs["A3"] = AttackJob("B3", 1)
    env.state.compromise_started_steps["A3"] = 2
    env.state.defenders["A"].inspection_findings["A3"] = InspectionFinding(True, 2)
    env.state.defenders["A"].monitoring_warnings["A3"] = MonitoringWarning(2)
    np.testing.assert_array_equal(before, env.encode_observation("B"))
    env.step({"A": ("isolate", "A1"), "B": ("wait", None)})
    b = named_vector(env, "B")
    assert b["server_1.peer_request_result.failed"] == 1
    assert b["server_1.warning_received"] == 0
    assert b["server_1.inspection_finding.unknown"] == 1


def test_encoding_is_pure_and_returns_new_storage():
    env = WorldEnvironment(world_settings())
    raw = env.observe("A")
    before_raw, before_state = deepcopy(raw), deepcopy(env.state)
    first = encode_defender_observation(raw, ["A1", "A2", "A3"], 50, 4)
    first[:] = 999
    assert raw == before_raw and env.state == before_state
    assert not np.any(env.encode_observation("A") == 999)


def test_explicit_server_order_overrides_dictionary_order():
    env = WorldEnvironment(world_settings())
    env.state.hosts["A3"].isolated = True
    raw = env.observe("A")
    raw["servers"] = dict(reversed(list(raw["servers"].items())))
    ordered = encode_defender_observation(raw, ["A1", "A2", "A3"], 50, 4)
    np.testing.assert_array_equal(ordered, env.encode_observation("A"))
    reordered = encode_defender_observation(raw, ["A3", "A1", "A2"], 50, 4)
    assert reordered[18] == 1 and reordered[46] == 0


def test_public_limits_change_scaling_not_categories():
    env = WorldEnvironment(world_settings())
    env.step({"A": ("restore", "A1"), "B": ("wait", None)})
    raw = env.observe("A")
    vector = encode_defender_observation(raw, ["A1", "A2", "A3"], 100, 6)
    assert vector[0] == pytest.approx(0.01)
    assert vector[11] == pytest.approx(0.5)
    assert vector[5] == 1


@pytest.mark.parametrize("field,value,error", [
    ("job_action", 5, ValueError), ("job_target", -1, ValueError),
    ("job_target", 4, ValueError), ("last_command_feedback", 9, ValueError),
    ("job_action", True, TypeError), ("job_target", 1.0, TypeError),
    ("elapsed_steps", -1, ValueError), ("elapsed_steps", 51, ValueError),
    ("job_remaining_steps", 5, ValueError), ("extra_detector_available", 2, ValueError),
])
def test_invalid_own_fields_raise(field, value, error):
    raw = WorldEnvironment(world_settings()).observe("A")
    raw[field] = value
    with pytest.raises(error, match=field):
        encode_defender_observation(raw, ["A1", "A2", "A3"], 50, 4)


@pytest.mark.parametrize("field,value,error", [
    ("service_running", 2, ValueError), ("isolated", False, TypeError),
    ("employee_request_result", 2, ValueError), ("peer_request_result", None, TypeError),
    ("warning_received", -1, ValueError), ("warning_age", -2, ValueError),
    ("inspection_finding", 3, ValueError), ("inspection_age", 51, ValueError),
])
def test_invalid_server_fields_raise(field, value, error):
    raw = WorldEnvironment(world_settings()).observe("A")
    raw["servers"]["A1"][field] = value
    with pytest.raises(error, match=field):
        encode_defender_observation(raw, ["A1", "A2", "A3"], 50, 4)


@pytest.mark.parametrize("limits,error", [((0, 4), ValueError), ((50, -1), ValueError),
                                           ((True, 4), TypeError), ((50, 4.0), TypeError)])
def test_invalid_limits_raise(limits, error):
    with pytest.raises(error):
        encode_defender_observation(WorldEnvironment(world_settings()).observe("A"), ["A1", "A2", "A3"], *limits)


def test_missing_server_does_not_silently_shorten_the_vector():
    raw = WorldEnvironment(world_settings()).observe("A")
    del raw["servers"]["A1"]
    with pytest.raises(ValueError, match="servers"):
        encode_defender_observation(raw, ["A1", "A2", "A3"], 50, 4)


@pytest.mark.parametrize("defender,error", [(None, TypeError), ("missing", ValueError)])
def test_wrapper_keeps_existing_defender_validation(defender, error):
    with pytest.raises(error, match="defender_id"):
        WorldEnvironment(world_settings()).encode_observation(defender)


def test_whole_episode_encoding_keeps_dynamics_and_width_then_reset():
    env, reference = WorldEnvironment(world_settings()), WorldEnvironment(world_settings())
    rng = random.Random(31)
    for interval in range(50):
        commands = {}
        for defender in ("A", "B"):
            named_vector(env, defender)
            if env.observe(defender)["job_remaining_steps"] == 0:
                commands[defender] = env.decode_action(defender, rng.randrange(13))
        assert env.step(commands) == reference.step(commands)
        assert env.state == reference.state
    for defender in ("A", "B"):
        assert named_vector(env, defender)["elapsed_fraction"] == 1
    env.reset()
    reference.reset()
    for defender in ("A", "B"):
        np.testing.assert_array_equal(env.encode_observation(defender), reference.encode_observation(defender))
