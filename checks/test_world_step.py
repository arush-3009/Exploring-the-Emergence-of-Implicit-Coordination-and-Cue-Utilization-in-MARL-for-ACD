from copy import deepcopy

import pytest

from actions.action_config import read_action_config
from actions.defender_actions import validate_defender_action
from attacker.attacker_config import read_attacker_config
from checks.scenario_helpers import TEST_WORLD, world_settings
from world.environment import WorldEnvironment
from world.state import AttackJob, FileRequestResult
from world.world_config import read_world_config


def successful_requests():
    routes = [
        ("EA", "A1"),
        ("EA", "A2"),
        ("EA", "A3"),
        ("EB", "B1"),
        ("EB", "B2"),
        ("EB", "B3"),
        ("A1", "B1"),
        ("B1", "A1"),
        ("A2", "B2"),
        ("B2", "A2"),
        ("A3", "B3"),
        ("B3", "A3"),
    ]
    return [
        {"source": source, "target": target, "succeeded": True}
        for source, target in routes
    ]


def wait_commands():
    return {"A": ("wait", None), "B": ("wait", None)}


def world_with_horizon(tmp_path, count):
    return WorldEnvironment(world_settings({"world.episode.max_steps": count}))


def test_two_wait_steps_start_then_finish_default_attack_with_one_clock_each():
    env = WorldEnvironment(world_settings())
    result = env.step(defender_commands=wait_commands())
    assert result == {
        "elapsed_steps": 1,
        "intrusion": None,
        "outages_started": [],
        "defender_command_results": {"A": "accepted", "B": "accepted"},
        "target_states_at_start": {"A": None, "B": None},
        "defender_completions": {},
        "attacks_started": {"A1": "B1"},
        "attack_completions": {},
        "request_results": successful_requests(),
        "monitoring_deliveries": {"A": {}, "B": {}},
        "reward": {
            "compromised_server_count": 1, "failed_request_count": 0,
            "compromise_cost_by_zone": {"A": 2.0, "B": 0.0},
            "compromise_cost": 2.0, "request_failure_cost": 0.0,
            "inspection_start_count": 0, "inspection_cost": 0.0,
            "shared_reward": -2.0,
        },
        "servers": {
            server: {"compromised": server == "A1", "isolated": False, "service_running": True, "vulnerable": True}
            for server in ("A1", "A2", "A3", "B1", "B2", "B3")
        },
        "episode_finished": False,
    }
    assert env.state.attack_jobs == {"A1": AttackJob("B1", 1)}
    assert not env.state.hosts["B1"].compromised
    result = env.step(wait_commands())
    assert result["elapsed_steps"] == 2
    assert result["attacks_started"] == {}
    assert result["attack_completions"] == {"A1": "succeeded"}
    assert env.state.attack_jobs == {}
    assert {key for key, host in env.state.hosts.items() if host.compromised} == {
        "A1",
        "B1",
    }
    assert env.step(wait_commands())["attack_completions"] == {}


def test_due_isolation_prevents_due_attack_and_feedback_keeps_both_stages():
    env = WorldEnvironment(world_settings())
    env.step(wait_commands())
    result = env.step({"A": ("wait", None), "B": ("isolate", "B1")})
    assert result["defender_command_results"]["B"] == "accepted"
    assert result["defender_completions"] == {"B": "isolate"}
    assert result["attack_completions"] == {"A1": "failed"}
    assert env.state.hosts["B1"].isolated
    assert not env.state.hosts["B1"].compromised
    assert env.state.attack_jobs == {}
    assert env.state.elapsed_steps == 2


def test_attack_starts_before_restore_immediate_effects_and_only_decrements_once():
    env = WorldEnvironment(world_settings())
    result = env.step({"A": ("restore", "A1"), "B": ("wait", None)})
    assert result["attacks_started"] == {"A1": "B1"}
    assert result["attack_completions"] == {}
    assert env.state.attack_jobs["A1"].remaining_steps == 1
    assert env.state.defenders["A"].job.remaining_steps == 3
    assert env.state.hosts["A1"].isolated
    assert env.state.hosts["A1"].compromised
    assert not env.state.hosts["A1"].file_service_running
    assert env.step({"B": ("wait", None)})["attack_completions"] == {"A1": "failed"}


def test_busy_defenders_are_omitted_and_newly_freed_defender_requires_next_choice():
    env = WorldEnvironment(world_settings())
    env.step({"A": ("inspect", "A1"), "B": ("restore", "B1")})
    result = env.step({})
    assert result["defender_command_results"] == {}
    assert result["defender_completions"] == {"A": "inspect"}
    assert env.state.defenders["B"].job.remaining_steps == 2
    before = deepcopy(env.state)
    with pytest.raises(ValueError, match="Missing commands.*A"):
        env.step({})
    assert env.state == before
    env.step({"A": ("wait", None)})
    result = env.step({"A": ("wait", None)})
    assert result["defender_completions"] == {"B": "restore"}
    assert env.state.defenders["A"].job is None
    assert env.state.defenders["B"].job is None
    assert env.state.elapsed_steps == 4


def test_valid_busy_command_is_rejected_without_stalling_existing_job():
    env = WorldEnvironment(world_settings())
    env.step({"A": ("inspect", "A1"), "B": ("wait", None)})
    result = env.step({"A": ("restore", "A1"), "B": ("wait", None)})
    assert result["defender_command_results"]["A"] == "rejected"
    assert result["defender_completions"] == {"A": "inspect"}
    assert env.state.defenders["A"].job is None
    assert not env.state.hosts["A1"].isolated
    assert env.state.hosts["A1"].file_service_running


@pytest.mark.parametrize(
    "commands,error",
    [
        (None, TypeError),
        ([], TypeError),
        ({"A": "wait", "B": ("wait", None)}, TypeError),
        ({"A": ["wait", None], "B": ("wait", None)}, TypeError),
        ({"A": ("wait",), "B": ("wait", None)}, ValueError),
        ({"A": ("wait", None, 2), "B": ("wait", None)}, ValueError),
        ({}, ValueError),
        ({"A": ("restore", "A1")}, ValueError),
        ({"A": ("restore", "A1"), "B": ("fly", "B1")}, ValueError),
        ({"A": ("restore", "A1"), "B": (4, "B1")}, TypeError),
        ({"A": ("restore", "A1"), "B": ("inspect", 4)}, TypeError),
        ({"A": ("restore", "A1"), "B": ("inspect", None)}, ValueError),
        ({"A": ("restore", "A1"), "B": ("inspect", "missing")}, ValueError),
        ({"A": ("restore", "A1"), "B": ("inspect", "A1")}, ValueError),
        ({"A": ("restore", "A1"), "B": ("inspect", "EB")}, ValueError),
        ({"A": ("restore", "A1"), "B": ("wait", "B1")}, ValueError),
        ({"A": ("restore", "A1"), 4: ("wait", None)}, TypeError),
        ({"A": ("restore", "A1"), "missing": ("wait", None)}, ValueError),
    ],
)
def test_bad_command_batch_raises_before_any_world_change(commands, error):
    env = WorldEnvironment(world_settings())
    before = deepcopy(env.state)
    with pytest.raises(error):
        env.step(commands)
    assert env.state == before


def test_bad_busy_command_still_raises_before_other_defender_can_start():
    env = WorldEnvironment(world_settings())
    env.step({"A": ("inspect", "A1"), "B": ("wait", None)})
    before = deepcopy(env.state)
    with pytest.raises(ValueError):
        env.step({"B": ("restore", "B1"), "A": ("fly", "A1")})
    assert env.state == before


def test_shared_validation_is_pure_and_start_checks_do_not_depend_on_compromise():
    env = WorldEnvironment(world_settings())
    config = read_action_config(TEST_WORLD / "action_config.toml")
    before = deepcopy((env.state, config))
    assert validate_defender_action(env.state, config, "A", "restore", "A1") is None
    assert (env.state, config) == before
    clean = WorldEnvironment(world_settings())
    clean.state.hosts["A1"].compromised = False
    commands = {"A": ("restore", "A1"), "B": ("reconnect", "B1")}
    assert (
        env.step(commands)["defender_command_results"]
        == clean.step(commands)["defender_command_results"]
    )


def test_command_insertion_order_does_not_change_outcome_or_input():
    first = WorldEnvironment(world_settings())
    second = WorldEnvironment(world_settings())
    commands = {"A": ("restore", "A1"), "B": ("inspect", "B1")}
    original = deepcopy(commands)
    assert first.step(commands) == second.step(dict(reversed(list(commands.items()))))
    assert first.state == second.state
    assert commands == original


def test_inspection_is_clean_at_d_but_host_infected_at_same_next_boundary():
    env = WorldEnvironment(world_settings())
    env.step({"A": ("wait", None), "B": ("inspect", "B1")})
    result = env.step({"A": ("wait", None)})
    assert result["defender_completions"] == {"B": "inspect"}
    assert result["attack_completions"] == {"A1": "succeeded"}
    finding = env.state.defenders["B"].inspection_findings["B1"]
    assert (finding.compromised, finding.completed_step) == (False, 2)
    assert env.state.hosts["B1"].compromised


def test_reconnection_opportunity_waits_until_next_step_then_reinfection_is_timed():
    env = WorldEnvironment(world_settings())
    env.step(wait_commands())
    env.step(wait_commands())
    env.step({"A": ("restore", "A1"), "B": ("wait", None)})
    for _ in range(3):
        env.step({"B": ("wait", None)})
    assert not env.state.hosts["A1"].compromised
    assert env.state.hosts["A1"].isolated
    result = env.step({"A": ("reconnect", "A1"), "B": ("wait", None)})
    assert result["attacks_started"] == {}
    assert env.state.attack_jobs == {}
    result = env.step(wait_commands())
    assert result["attacks_started"] == {"B1": "A1"}
    assert env.state.attack_jobs["B1"].remaining_steps == 1
    result = env.step(wait_commands())
    assert result["attack_completions"] == {"B1": "succeeded"}
    assert env.state.elapsed_steps == 9


def test_no_restart_after_completion_inside_the_same_step_even_with_one_step_attacks(
    tmp_path,
):
    path = tmp_path / "attack.toml"
    path.write_text("[spread]\nduration_steps = 1\n")
    env = WorldEnvironment(world_settings({"attacker": read_attacker_config(path)}))
    result = env.step(wait_commands())
    assert result["attacks_started"] == {"A1": "B1"}
    assert result["attack_completions"] == {"A1": "succeeded"}
    assert env.state.attack_jobs == {}
    env = WorldEnvironment(world_settings({"attacker": read_attacker_config(path)}))
    result = env.step({"A": ("restore", "A1"), "B": ("wait", None)})
    assert result["attack_completions"] == {"A1": "failed"}
    assert env.state.attack_jobs == {}


def test_default_horizon_exactly_50_steps_no_extra_transition_and_reset_reopens():
    env = WorldEnvironment(world_settings())
    for boundary in range(1, 51):
        result = env.step(wait_commands())
        assert result["elapsed_steps"] == boundary
        assert result["episode_finished"] is (boundary == 50)
    before = deepcopy(env.state)
    with pytest.raises(RuntimeError, match="reset"):
        env.step(wait_commands())
    assert env.state == before
    env.reset()
    assert env.state.elapsed_steps == 0
    assert env.step(wait_commands())["episode_finished"] is False


def test_final_interval_resolves_due_attack_before_reporting_end(tmp_path):
    env = world_with_horizon(tmp_path, 2)
    env.step(wait_commands())
    result = env.step(wait_commands())
    assert result["episode_finished"]
    assert result["attack_completions"] == {"A1": "succeeded"}
    assert env.state.hosts["B1"].compromised


def test_horizon_does_not_flush_unfinished_jobs_or_apply_their_remaining_effects(
    tmp_path,
):
    env = world_with_horizon(tmp_path, 1)
    result = env.step({"A": ("restore", "A1"), "B": ("wait", None)})
    assert result["episode_finished"]
    assert result["defender_completions"] == {}
    assert result["attack_completions"] == {}
    assert env.state.defenders["A"].job.remaining_steps == 3
    assert env.state.attack_jobs["A1"].remaining_steps == 1
    assert env.state.hosts["A1"].compromised
    assert not env.state.hosts["A1"].file_service_running


def test_no_early_end_when_all_hosts_clean_and_wait_still_advances():
    env = WorldEnvironment(world_settings())
    env.state.hosts["A1"].compromised = False
    before = deepcopy(env.state)
    result = env.step(wait_commands())
    assert not result["episode_finished"]
    assert result["attacks_started"] == {}
    before.elapsed_steps = 1
    before.request_results = [FileRequestResult(**row) for row in successful_requests()]
    before.compromise_started_steps.clear()
    for defender in before.defenders.values():
        defender.last_command_feedback = "accepted"
    assert env.state == before


def test_result_is_detached_bookkeeping_and_old_reports_do_not_change():
    env = WorldEnvironment(world_settings())
    result = env.step(wait_commands())
    snapshot = deepcopy(result)
    env.step(wait_commands())
    assert result == snapshot
    result["attacks_started"].clear()
    result["elapsed_steps"] = 700
    assert env.state.elapsed_steps == 2
    assert env.state.hosts["B1"].compromised


def test_corrupt_stored_attack_job_stops_before_defender_start_effects():
    env = WorldEnvironment(world_settings())
    env.state.attack_jobs["A1"] = AttackJob("missing", 1)
    before = deepcopy(env.state)
    with pytest.raises(ValueError):
        env.step({"A": ("restore", "A1"), "B": ("wait", None)})
    assert env.state == before


def test_custom_ids_and_pairings_are_used_by_the_step(tmp_path):
    source = TEST_WORLD / "world_config.toml"
    config = source.read_text()
    for old, new in [("A", "X"), ("B", "Y")]:
        config = config.replace(f"zones.{old}", f"zones.{new}")
        config = config.replace(f'"E{old}"', f'"E{new}"')
        for number in (1, 2, 3):
            config = config.replace(f'"{old}{number}"', f'"{new}{number}"')
    path = tmp_path / "world.toml"
    path.write_text(config)
    with pytest.raises(ValueError, match="unknown zone"):
        WorldEnvironment(world_settings({"world": read_world_config(path)}))
    env = WorldEnvironment(world_settings({"world": read_world_config(path),
                                           "observations.monitoring.extra_detector_zones": ["X"]}))
    choices = {"X": ("wait", None), "Y": ("wait", None)}
    assert env.step(choices)["attacks_started"] == {"X1": "Y1"}
    assert env.step(choices)["attack_completions"] == {"X1": "succeeded"}
