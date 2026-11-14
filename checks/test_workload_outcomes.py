from copy import deepcopy
from dataclasses import FrozenInstanceError, asdict

import pytest

from checks.scenario_helpers import world_settings
from workload.workload_config import read_workload_config
from world.environment import WorldEnvironment


def waits():
    return {"A": ("wait", None), "B": ("wait", None)}


def failures(results):
    return {(r.source, r.target) for r in results if not r.succeeded}


def test_initial_none_yet_then_all_work_succeeds_despite_compromise():
    env = WorldEnvironment(world_settings())
    assert env.state.request_results == []
    results = env.run_workload()
    assert len(results) == 12 and all(r.succeeded for r in results)
    assert env.state.hosts["A1"].compromised
    assert not env.state.hosts["EA"].has_file_service
    assert env.state.request_results == results
    assert env.state.elapsed_steps == 0


@pytest.mark.parametrize(
    "isolated, expected",
    [
        (["A1"], {("EA", "A1"), ("A1", "B1"), ("B1", "A1")}),
        (["A1", "B1"], {("EA", "A1"), ("EB", "B1"), ("A1", "B1"), ("B1", "A1")}),
        (["EA"], {("EA", "A1"), ("EA", "A2"), ("EA", "A3")}),
    ],
)
def test_isolation_affects_only_expected_operations_and_each_fails_once(
    isolated, expected
):
    env = WorldEnvironment(world_settings())
    for host in isolated:
        env.state.hosts[host].isolated = True
    results = env.run_workload()
    assert len(results) == 12
    assert failures(results) == expected
    assert sum(not r.succeeded for r in results) == len(expected)


@pytest.mark.parametrize("stopped", [["A1"], ["A1", "B1"]])
def test_stopped_server_cannot_send_or_serve_even_when_connected(stopped):
    env = WorldEnvironment(world_settings())
    for host in stopped:
        env.state.hosts[host].file_service_running = False
    expected = {("EA", "A1"), ("A1", "B1"), ("B1", "A1")}
    if "B1" in stopped:
        expected.add(("EB", "B1"))
    assert failures(env.run_workload()) == expected


def test_all_blocked_keeps_all_requests_with_no_duplicate_failure_accounting():
    env = WorldEnvironment(world_settings())
    for host in env.state.hosts.values():
        host.isolated = True
        host.file_service_running = False
    results = env.run_workload()
    assert len(results) == 12
    assert sum(not r.succeeded for r in results) == 12


def test_compromise_and_vulnerability_never_determine_business_outcomes():
    env = WorldEnvironment(world_settings())
    for host in env.state.hosts.values():
        if host.has_file_service:
            host.compromised = True
            host.vulnerable = False
    assert all(r.succeeded for r in env.run_workload())


def test_workload_only_changes_results_and_returns_a_detached_list_of_frozen_records():
    env = WorldEnvironment(world_settings())
    before = deepcopy(env.state)
    results = env.run_workload()
    assert env.state.hosts == before.hosts
    assert env.state.defenders == before.defenders
    assert env.state.attack_jobs == before.attack_jobs
    assert env.state.elapsed_steps == before.elapsed_steps
    with pytest.raises(FrozenInstanceError):
        results[0].succeeded = False
    results.clear()
    assert len(env.state.request_results) == 12


def test_results_replaced_each_interval_and_reset_independent_across_worlds():
    env, other = WorldEnvironment(world_settings()), WorldEnvironment(world_settings())
    old = env.run_workload()
    env.state.hosts["A1"].isolated = True
    new = env.run_workload()
    assert all(r.succeeded for r in old)
    assert len(failures(new)) == 3
    assert len(env.state.request_results) == 12
    previous = env.state
    env.reset()
    assert env.state.request_results == other.state.request_results == []
    assert env.state.request_results is not other.state.request_results
    assert previous.request_results == new


def test_missing_world_record_raises_instead_of_becoming_work_failure():
    env = WorldEnvironment(world_settings())
    env.run_workload()
    old = deepcopy(env.state.request_results)
    del env.state.hosts["B3"]
    with pytest.raises(KeyError):
        env.run_workload()
    assert env.state.request_results == old


def test_step_isolate_reconnect_trace_and_report_do_not_alias_state():
    env = WorldEnvironment(world_settings())
    reports = []
    for action in ["wait", "isolate", "reconnect"]:
        reports.append(
            env.step(
                {"A": (action, None if action == "wait" else "A1"), "B": ("wait", None)}
            )
        )
    assert [r["elapsed_steps"] for r in reports] == [1, 2, 3]
    assert [
        sum(not row["succeeded"] for row in r["request_results"]) for r in reports
    ] == [0, 3, 0]
    assert reports[1]["attack_completions"] == {"A1": "failed"}
    assert all(r.succeeded for r in env.state.request_results)
    assert reports[-1]["request_results"] == [
        asdict(r) for r in env.state.request_results
    ]
    reports[-1]["request_results"][0]["succeeded"] = False
    reports[-1]["request_results"].clear()
    assert (
        len(env.state.request_results) == 12 and env.state.request_results[0].succeeded
    )


def test_restore_blocks_immediately_and_after_completion_until_reconnection():
    env = WorldEnvironment(world_settings())
    reports = [env.step({"A": ("restore", "A1"), "B": ("wait", None)})]
    reports += [env.step({"B": ("wait", None)}) for _ in range(3)]
    assert all(
        sum(not r["succeeded"] for r in report["request_results"]) == 3
        for report in reports
    )
    assert reports[-1]["defender_completions"] == {"A": "restore"}
    assert env.state.hosts["A1"].file_service_running
    assert not env.state.hosts["A1"].compromised
    report = env.step({"A": ("reconnect", "A1"), "B": ("wait", None)})
    assert all(r["succeeded"] for r in report["request_results"])


def test_due_attack_precedes_workload_and_infection_does_not_stop_service(monkeypatch):
    env = WorldEnvironment(world_settings())
    env.step(waits())
    actual = env.run_workload

    def observe_order():
        assert env.state.hosts["B1"].compromised
        assert env.state.attack_jobs == {}
        assert env.state.elapsed_steps == 1
        return actual()

    monkeypatch.setattr(env, "run_workload", observe_order)
    report = env.step(waits())
    assert report["attack_completions"] == {"A1": "succeeded"}
    assert all(r["succeeded"] for r in report["request_results"])
    assert env.state.elapsed_steps == 2


def test_custom_demand_loads_once_and_counts_each_repeated_operation(tmp_path):
    path = tmp_path / "workload.toml"
    path.write_text("[requests]\nper_route_per_interval = 2\n")
    env = WorldEnvironment(world_settings({"workload": read_workload_config(path)}))
    path.write_text("[requests]\nper_route_per_interval = 1\n")
    for _ in range(2):
        env.reset()
        report = env.step({"A": ("isolate", "A1"), "B": ("wait", None)})
        assert len(report["request_results"]) == 24
        assert sum(not r["succeeded"] for r in report["request_results"]) == 6
    assert len(WorldEnvironment(world_settings({"workload": read_workload_config(path)})).run_workload()) == 12


def test_invalid_workload_fails_environment_construction(tmp_path):
    path = tmp_path / "invalid_workload.toml"
    path.write_text("[requests]\nper_route_per_interval = 0\n")
    with pytest.raises(ValueError, match="invalid_workload.toml"):
        WorldEnvironment(world_settings({"workload": read_workload_config(path)}))


def test_workload_runs_on_last_interval_but_not_after_episode_end(tmp_path):
    env = WorldEnvironment(world_settings({"world.episode.max_steps": 1}))
    report = env.step({"A": ("isolate", "A1"), "B": ("isolate", "B1")})
    assert report["episode_finished"]
    assert sum(not r["succeeded"] for r in report["request_results"]) == 4
    before = deepcopy(env.state)
    with pytest.raises(RuntimeError):
        env.step(waits())
    assert env.state == before
