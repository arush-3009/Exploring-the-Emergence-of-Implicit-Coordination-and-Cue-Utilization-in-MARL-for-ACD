from copy import deepcopy

import pytest

from checks.scenario_helpers import TEST_WORLD, world_settings
from observations.defender_observation import build_defender_observation
from observations.observation_config import read_observation_config
from observations.schema import observation_feature_names
from world.environment import WorldEnvironment
from world.state import AttackJob, InspectionFinding, MonitoringWarning
from world.world_config import read_world_config

WAIT = {"A": ("wait", None), "B": ("wait", None)}
SERVER_FIELDS = [
    "service_running",
    "isolated",
    "employee_request_result",
    "peer_request_result",
    "warning_received",
    "warning_age",
    "inspection_finding",
    "inspection_age",
]


def test_reset_has_exact_fixed_local_schema_and_unknown_evidence():
    env = WorldEnvironment(world_settings())
    for zone, extra in [("A", 1), ("B", 0)]:
        observation = env.observe(zone)
        assert observation == {
            "elapsed_steps": 0,
            "extra_detector_available": extra,
            "job_action": 0,
            "job_target": 0,
            "job_remaining_steps": 0,
            "last_command_feedback": 0,
            "servers": {
                zone + str(i): {
                    "service_running": 1,
                    "isolated": 0,
                    "employee_request_result": -1,
                    "peer_request_result": -1,
                    "warning_received": 0,
                    "warning_age": -1,
                    "inspection_finding": -1,
                    "inspection_age": -1,
                }
                for i in range(1, 4)
            },
        }
        assert list(observation["servers"]) == [zone + str(i) for i in range(1, 4)]
        values = [value for key, value in observation.items() if key != "servers"]
        for server in observation["servers"].values():
            assert list(server) == SERVER_FIELDS
            values.extend(server.values())
        assert len(values) == 30 and all(type(value) is int for value in values)


def test_reading_does_not_mutate_consume_or_alias_records():
    env = WorldEnvironment(world_settings())
    env.step(WAIT)
    env.step(WAIT)
    before = deepcopy(env.state)
    observation = env.observe("A")
    assert env.observe("A") == observation
    observation["servers"]["A1"]["warning_age"] = 999
    observation["last_command_feedback"] = 999
    assert env.state == before
    assert env.observe("A")["servers"]["A1"]["warning_age"] == 0


def test_full_boundary_trace_distinguishes_infection_age_from_warning_age():
    env = WorldEnvironment(world_settings())
    expected_a = {1: -1, 2: 0, 3: 1, 4: 2, 5: 3, 6: 0, 7: 1, 8: 2}
    for k in range(1, 9):
        env.step(WAIT)
        a, b = env.observe("A"), env.observe("B")
        assert a["elapsed_steps"] == b["elapsed_steps"] == k
        assert a["servers"]["A1"]["warning_age"] == expected_a[k]
        assert b["servers"]["B1"]["warning_age"] == (0 if k == 8 else -1)
        assert a["servers"]["A1"]["peer_request_result"] == 1
        assert b["servers"]["B1"]["inspection_finding"] == -1


def test_cue_is_local_request_outcome_without_remote_action_or_cause():
    env = WorldEnvironment(world_settings())
    env.step(WAIT)
    env.step(WAIT)
    env.step({"A": ("isolate", "A1"), "B": ("wait", None)})
    b = env.observe("B")["servers"]["B1"]
    assert b == {
        "service_running": 1,
        "isolated": 0,
        "employee_request_result": 1,
        "peer_request_result": 0,
        "warning_received": 0,
        "warning_age": -1,
        "inspection_finding": -1,
        "inspection_age": -1,
    }
    other = WorldEnvironment(world_settings())
    other.step(WAIT)
    other.step(WAIT)
    other.step({"A": ("restore", "A1"), "B": ("wait", None)})
    assert other.observe("B") == env.observe("B")


def test_hidden_and_teammate_changes_cannot_change_current_observation():
    env = WorldEnvironment(world_settings())
    env.step(WAIT)
    env.step(WAIT)
    original = env.observe("B")
    for host in env.state.hosts.values():
        host.compromised = not host.compromised
        host.vulnerable = not host.vulnerable
        if host.zone == "A":
            host.isolated = not host.isolated
            host.file_service_running = not host.file_service_running
    env.state.compromise_started_steps = {"A3": 99}
    env.state.attack_jobs = {"A2": AttackJob("B2", 30)}
    env.state.defenders["A"].inspection_findings["A1"] = InspectionFinding(False, 2)
    env.state.defenders["A"].monitoring_warnings["A3"] = MonitoringWarning(2)
    env.state.defenders["A"].last_command_feedback = "rejected"
    assert env.observe("B") == original


def test_inspection_can_be_stale_even_at_age_zero_after_attack_resolution():
    env = WorldEnvironment(world_settings())
    env.step({"A": ("wait", None), "B": ("inspect", "B1")})
    first = env.observe("B")
    assert (first["job_action"], first["job_target"], first["job_remaining_steps"]) == (
        1,
        1,
        1,
    )
    assert first["last_command_feedback"] == 2
    env.step({"A": ("wait", None)})
    second = env.observe("B")
    assert env.state.hosts["B1"].compromised
    assert second["servers"]["B1"]["inspection_finding"] == 0
    assert second["servers"]["B1"]["inspection_age"] == 0
    assert (
        second["job_action"],
        second["job_target"],
        second["job_remaining_steps"],
    ) == (0, 0, 0)
    assert second["last_command_feedback"] == 1


def test_restore_retires_its_old_findings_and_warnings():
    env = WorldEnvironment(world_settings())
    env.step({"A": ("inspect", "A1"), "B": ("wait", None)})
    env.step({"B": ("wait", None)})
    env.step({"A": ("restore", "A1"), "B": ("wait", None)})
    for _ in range(3):
        env.step({"B": ("wait", None)})
    a = env.observe("A")["servers"]["A1"]
    assert not env.state.hosts["A1"].compromised
    assert (a["inspection_finding"], a["inspection_age"]) == (-1, -1)
    assert (a["warning_received"], a["warning_age"]) == (0, -1)
    assert (a["isolated"], a["service_running"]) == (1, 1)


def test_feedback_is_latest_only_and_completion_wins_over_start_or_rejection():
    env = WorldEnvironment(world_settings())
    env.step({"A": ("restore", "A1"), "B": ("wait", None)})
    assert env.observe("A")["last_command_feedback"] == 2
    assert env.observe("A")["job_action"] == 3
    env.step({"B": ("wait", None)})
    assert env.observe("A")["last_command_feedback"] == 0
    env.step(WAIT)
    assert env.observe("A")["last_command_feedback"] == 4
    report = env.step(WAIT)
    assert report["defender_command_results"]["A"] == "rejected"
    assert env.observe("A")["last_command_feedback"] == 1
    env.step({"A": ("isolate", "A1"), "B": ("wait", None)})
    assert env.observe("A")["last_command_feedback"] == 3
    env.step({"A": ("reconnect", "A1"), "B": ("wait", None)})
    assert env.observe("A")["last_command_feedback"] == 1
    env.step(WAIT)
    assert env.observe("A")["last_command_feedback"] == 2


def test_same_schema_after_terminal_boundary_and_reset_clears_own_feedback():
    env = WorldEnvironment(world_settings())
    initial = env.observe("A")
    for _ in range(50):
        env.step(WAIT)
    terminal = env.observe("A")
    assert terminal["elapsed_steps"] == 50
    assert terminal["servers"]["A1"]["warning_age"] == 44
    assert list(terminal) == list(initial)
    env.reset()
    assert env.observe("A") == initial


def test_order_and_target_indices_follow_selected_config_not_dict_insertion():
    world = read_world_config(TEST_WORLD / "world_config.toml")
    world["zones"]["A"]["servers"] = ["A3", "A1", "A2"]
    observations = read_observation_config(world, TEST_WORLD / "observation_config.toml")
    env = WorldEnvironment(world_settings())
    env.step({"A": ("inspect", "A2"), "B": ("wait", None)})
    env.state.hosts = dict(reversed(list(env.state.hosts.items())))
    result = build_defender_observation(env.state, world, observations, "A")
    assert list(result["servers"]) == ["A3", "A1", "A2"]
    assert result["job_target"] == 3


@pytest.mark.parametrize(
    "defender_id,error", [(1, TypeError), ([], TypeError), ("C", ValueError)]
)
def test_invalid_defender_raises_without_mutation(defender_id, error):
    env = WorldEnvironment(world_settings())
    before = deepcopy(env.state)
    with pytest.raises(error):
        env.observe(defender_id)
    assert env.state == before


@pytest.mark.parametrize(
    "stamp,error",
    [(True, TypeError), (1.5, TypeError), (-1, ValueError), (3, ValueError)],
)
def test_corrupt_warning_record_is_not_silently_treated_as_unknown(stamp, error):
    env = WorldEnvironment(world_settings())
    env.step(WAIT)
    env.step(WAIT)
    env.state.defenders["A"].monitoring_warnings["A1"] = MonitoringWarning(stamp)
    with pytest.raises(error):
        env.observe("A")


def test_partial_work_batch_is_an_error_not_unknown_local_evidence():
    env = WorldEnvironment(world_settings())
    env.step(WAIT)
    env.state.request_results = [
        r for r in env.state.request_results if r.source != "EA"
    ]
    with pytest.raises(KeyError):
        env.observe("A")


@pytest.mark.parametrize("reason", ["reset", "wait", "completed", "already_satisfied"])
def test_no_job_status_does_not_mean_the_defender_chose_wait(reason):
    env = WorldEnvironment(world_settings())
    if reason == "wait":
        env.step(WAIT)
    elif reason == "completed":
        env.step({"A": ("inspect", "A1"), "B": ("wait", None)})
        assert env.observe("A")["job_action"] == 1
        env.step({"B": ("wait", None)})
    elif reason == "already_satisfied":
        env.step({"A": ("reconnect", "A1"), "B": ("wait", None)})
    observation = env.observe("A")
    assert env.state.defenders["A"].job is None
    assert (observation["job_action"], observation["job_target"],
            observation["job_remaining_steps"]) == (0, 0, 0)
    expected_feedback = {"reset": 0, "wait": 2, "completed": 1, "already_satisfied": 3}
    assert observation["last_command_feedback"] == expected_feedback[reason]


@pytest.mark.parametrize("busy", [False, True])
def test_free_is_not_a_command_even_when_busy(busy):
    env = WorldEnvironment(world_settings())
    if busy:
        env.step({"A": ("inspect", "A1"), "B": ("wait", None)})
    before = deepcopy(env.state)
    with pytest.raises(ValueError, match="Unknown action"):
        env.step({"A": ("free", None), "B": ("wait", None)})
    assert env.state == before


def masked_world(tmp_path, defenders):
    return WorldEnvironment(world_settings({"observations.masks.hide_peer_request_result": list(defenders)}))


def test_a_masked_defender_sees_unknown_peer_results_while_everything_else_is_the_same(tmp_path):
    plain, masked = WorldEnvironment(world_settings()), masked_world(tmp_path, ["B"])
    for env in (plain, masked):
        env.step(WAIT)
        env.step(WAIT)
        env.step({"A": ("isolate", "A1"), "B": ("wait", None)})
    plain_b, masked_b = plain.observe("B"), masked.observe("B")
    assert plain_b["servers"]["B1"]["peer_request_result"] == 0
    assert masked_b["servers"]["B1"]["peer_request_result"] == -1
    for server in ("B1", "B2", "B3"):
        for field, value in plain_b["servers"][server].items():
            if field != "peer_request_result":
                assert masked_b["servers"][server][field] == value
    assert {k: v for k, v in masked_b.items() if k != "servers"} == {k: v for k, v in plain_b.items() if k != "servers"}
    assert masked.observe("A")["servers"]["A1"]["peer_request_result"] == plain.observe("A")["servers"]["A1"]["peer_request_result"] == 0
    names = list(observation_feature_names(3))
    vector = masked.encode_observation("B")
    assert [vector[names.index(f"server_1.peer_request_result.{c}")] for c in ("unknown", "failed", "succeeded")] == [1.0, 0.0, 0.0]
    plain_vector = plain.encode_observation("B")
    assert [plain_vector[names.index(f"server_1.peer_request_result.{c}")] for c in ("unknown", "failed", "succeeded")] == [0.0, 1.0, 0.0]


def test_hiding_the_cue_changes_no_report_reward_or_state(tmp_path):
    plain, masked = WorldEnvironment(world_settings()), masked_world(tmp_path, ["A", "B"])
    commands = [WAIT, WAIT, {"A": ("restore", "A1"), "B": ("wait", None)}, WAIT, WAIT, WAIT,
                {"A": ("reconnect", "A1"), "B": ("restore", "B1")}, WAIT, WAIT, WAIT, WAIT]
    for command in commands:
        assert plain.step(command) == masked.step(command)
    assert plain.state == masked.state
    for defender in ("A", "B"):
        assert masked.observe(defender)["servers"]["A1" if defender == "A" else "B1"]["peer_request_result"] == -1


def suppressed_world(tmp_path, defenders):
    return WorldEnvironment(world_settings({"observations.masks.suppress_peer_failures_when_local_available": defenders}))


@pytest.mark.parametrize("running, isolated, expected", [(True, False, 1), (False, False, 0),
                                                       (True, True, 0), (False, True, 0)])
def test_failure_suppression_uses_only_local_availability(tmp_path, running, isolated, expected):
    plain, suppressed = WorldEnvironment(world_settings()), suppressed_world(tmp_path, ["B"])
    assert suppressed.observe("B") == plain.observe("B")
    for env in (plain, suppressed):
        env.state.hosts["B1"].file_service_running = running
        env.state.hosts["B1"].isolated = isolated
    command = {"A": ("isolate", "A1"), "B": ("wait", None)}
    assert plain.step(command) == suppressed.step(command)
    before = deepcopy(suppressed.state)
    expected_observation = plain.observe("B")
    assert expected_observation["servers"]["B1"]["peer_request_result"] == 0
    expected_observation["servers"]["B1"]["peer_request_result"] = expected
    assert suppressed.observe("B") == expected_observation
    assert suppressed.observe("A") == plain.observe("A")
    assert suppressed.state == before == plain.state
    names = list(observation_feature_names(3))
    vector = suppressed.encode_observation("B")
    assert vector[names.index("server_1.peer_request_result.succeeded")] == expected
    assert vector[names.index("server_1.peer_request_result.failed")] == 1 - expected


@pytest.mark.parametrize("defenders", [[], ["B"]])
def test_suppression_preserves_physical_transitions_rewards_and_default_observations(tmp_path, defenders):
    plain, suppressed = WorldEnvironment(world_settings()), suppressed_world(tmp_path, defenders)
    commands = [WAIT, WAIT, {"A": ("restore", "A1"), "B": ("wait", None)}, WAIT, WAIT, WAIT,
                {"A": ("reconnect", "A1"), "B": ("restore", "B1")}, WAIT, WAIT, WAIT,
                {"A": ("wait", None), "B": ("reconnect", "B1")}, WAIT]
    for command in commands:
        assert plain.step(command) == suppressed.step(command)
        assert plain.state == suppressed.state
        assert plain.observe("A") == suppressed.observe("A")
        if not defenders:
            assert plain.observe("B") == suppressed.observe("B")
        elif not plain.observe("B")["servers"]["B1"]["service_running"]:
            assert suppressed.observe("B")["servers"]["B1"]["peer_request_result"] == 0
    assert suppressed.observe("B")["servers"]["B1"]["peer_request_result"] == 1
