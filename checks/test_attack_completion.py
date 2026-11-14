from copy import deepcopy

import pytest

from actions.defender_actions import advance_defender_jobs
from attacker.attacker_config import read_attacker_config
from attacker.scripted_attacker import advance_attack_jobs, start_attack_jobs
from checks.scenario_helpers import TEST_WORLD, world_settings
from world.environment import WorldEnvironment
from world.state import AttackJob, DefenderJob, create_initial_state
from world.world_config import read_world_config


def test_default_attempt_finishes_after_two_calls_and_changes_only_target_control():
    env = WorldEnvironment(world_settings())
    env.start_attacks()
    before = deepcopy(env.state)
    job = env.state.attack_jobs["A1"]
    assert env.advance_attacks() == {}
    before.attack_jobs["A1"].remaining_steps = 1
    assert env.state == before
    assert env.state.attack_jobs["A1"] is job
    assert env.advance_attacks() == {"A1": "succeeded"}
    before.attack_jobs.clear()
    before.hosts["B1"].compromised = True
    assert env.state == before
    assert env.advance_attacks() == {}
    assert env.state == before


@pytest.mark.parametrize("duration", [1, 3, 5])
def test_timer_copied_at_start_controls_exact_completion(duration, tmp_path):
    path = tmp_path / "attacker.toml"
    path.write_text(f"[spread]\nduration_steps = {duration}\n")
    env = WorldEnvironment(world_settings({"attacker": read_attacker_config(path)}))
    env.start_attacks()
    path.write_text("[spread]\nduration_steps = 9\n")
    for remaining in range(duration - 1, 0, -1):
        assert env.advance_attacks() == {}
        assert env.state.attack_jobs["A1"].remaining_steps == remaining
        assert not env.state.hosts["B1"].compromised
    assert env.advance_attacks() == {"A1": "succeeded"}
    assert env.state.elapsed_steps == 0


@pytest.mark.parametrize(
    "host,field,value",
    [
        ("A1", "compromised", False),
        ("A1", "isolated", True),
        ("B1", "compromised", True),
        ("B1", "isolated", True),
        ("B1", "has_file_service", False),
        ("B1", "file_service_running", False),
        ("B1", "vulnerable", False),
    ],
)
def test_due_failure_clears_attempt_without_any_host_or_clock_change(
    host, field, value
):
    env = WorldEnvironment(world_settings())
    env.start_attacks()
    env.advance_attacks()
    setattr(env.state.hosts[host], field, value)
    before = deepcopy(env.state)
    assert env.advance_attacks() == {"A1": "failed"}
    before.attack_jobs.clear()
    assert env.state == before


def test_changed_conditions_do_not_cancel_early_and_only_due_conditions_count():
    env = WorldEnvironment(world_settings())
    env.start_attacks()
    env.state.hosts["B1"].isolated = True
    assert env.advance_attacks() == {}
    assert env.state.attack_jobs["A1"].remaining_steps == 1
    env.state.hosts["B1"].isolated = False
    assert env.advance_attacks() == {"A1": "succeeded"}


def test_source_service_and_vulnerability_are_not_completion_requirements():
    env = WorldEnvironment(world_settings())
    env.start_attacks()
    env.state.hosts["A1"].file_service_running = False
    env.state.hosts["A1"].vulnerable = False
    env.advance_attacks()
    assert env.advance_attacks() == {"A1": "succeeded"}


def test_mixed_pending_failed_and_successful_jobs_all_advance_once():
    env = WorldEnvironment(world_settings())
    env.state.hosts["A2"].compromised = True
    env.state.hosts["B3"].compromised = True
    env.start_attacks()
    env.state.attack_jobs["A1"].remaining_steps = 1
    env.state.attack_jobs["B3"].remaining_steps = 1
    env.state.hosts["A3"].isolated = True
    assert env.advance_attacks() == {"A1": "succeeded", "B3": "failed"}
    assert env.state.attack_jobs == {"A2": AttackJob("B2", 1)}
    assert env.state.hosts["B1"].compromised
    assert not env.state.hosts["B2"].compromised
    assert not env.state.hosts["A3"].compromised


@pytest.mark.parametrize("reverse_order", [False, True])
def test_stored_job_order_does_not_change_paired_outcomes(reverse_order):
    env = WorldEnvironment(world_settings())
    jobs = [("A1", AttackJob("B1", 1)), ("B1", AttackJob("A1", 1))]
    env.state.attack_jobs = dict(reversed(jobs) if reverse_order else jobs)
    assert env.advance_attacks() == {"A1": "succeeded", "B1": "failed"}
    assert env.state.attack_jobs == {}


@pytest.mark.parametrize("zone,target", [("A", "A1"), ("B", "B1")])
def test_defender_isolation_at_d_blocks_attack_due_in_the_same_interval(zone, target):
    env = WorldEnvironment(world_settings())
    env.start_attacks()
    env.advance_attacks()
    env.start_action(zone, "isolate", target)
    assert advance_defender_jobs(env.state, env._action_config) == {zone: "isolate"}
    assert env.advance_attacks() == {"A1": "failed"}
    assert not env.state.hosts["B1"].compromised


def test_immediate_restore_effects_block_due_attack_before_cleanup_finishes():
    env = WorldEnvironment(world_settings())
    env.start_attacks()
    env.advance_attacks()
    env.start_action("A", "restore", "A1")
    assert advance_defender_jobs(env.state, env._action_config) == {}
    assert env.state.hosts["A1"].compromised
    assert env.advance_attacks() == {"A1": "failed"}
    assert env.state.defenders["A"].job.remaining_steps == 3


def test_restore_completion_before_attack_keeps_target_clean_and_isolated():
    env = WorldEnvironment(world_settings())
    env.start_attacks()
    env.advance_attacks()
    env.start_action("B", "restore", "B1")
    env.state.defenders["B"].job.remaining_steps = 1
    assert advance_defender_jobs(env.state, env._action_config) == {"B": "restore"}
    assert env.advance_attacks() == {"A1": "failed"}
    assert env.state.hosts["B1"].file_service_running
    assert env.state.hosts["B1"].isolated
    assert not env.state.hosts["B1"].compromised


def test_inspection_snapshot_precedes_same_interval_infection_and_stays_clean():
    env = WorldEnvironment(world_settings())
    env.start_attacks()
    env.start_action("B", "inspect", "B1")
    for _ in range(2):
        advance_defender_jobs(env.state, env._action_config)
        env.advance_attacks()
        env.state.elapsed_steps += 1
    finding = env.state.defenders["B"].inspection_findings["B1"]
    assert (finding.compromised, finding.completed_step) == (False, 2)
    assert env.state.hosts["B1"].compromised


def test_failure_is_removed_and_retry_only_starts_on_an_explicit_later_start_call():
    env = WorldEnvironment(world_settings())
    env.start_attacks()
    env.state.hosts["B1"].isolated = True
    env.advance_attacks()
    assert env.advance_attacks() == {"A1": "failed"}
    env.state.hosts["B1"].isolated = False
    assert env.advance_attacks() == {}
    assert env.start_attacks() == {"A1": "B1"}
    assert env.state.attack_jobs["A1"].remaining_steps == 2


def test_success_creates_no_chain_job_and_peer_can_reinfect_after_restore_reconnect():
    env = WorldEnvironment(world_settings())
    env.start_attacks()
    env.advance_attacks()
    env.advance_attacks()
    assert env.state.attack_jobs == {}
    env.start_action("A", "restore", "A1")
    for _ in range(4):
        advance_defender_jobs(env.state, env._action_config)
        env.state.elapsed_steps += 1
    assert env.start_attacks() == {}
    env.start_action("A", "reconnect", "A1")
    advance_defender_jobs(env.state, env._action_config)
    env.state.elapsed_steps += 1
    assert env.start_attacks() == {"B1": "A1"}
    env.advance_attacks()
    assert env.advance_attacks() == {"B1": "succeeded"}
    assert env.state.hosts["A1"].compromised


def test_with_patching_on_the_peer_cannot_reinfect_after_restore_reconnect():
    env = WorldEnvironment(world_settings())
    patching = deepcopy(env._action_config)
    patching["restore"]["patches_server"] = True
    env.start_attacks()
    env.advance_attacks()
    env.advance_attacks()
    env.start_action("A", "restore", "A1")
    for _ in range(4):
        advance_defender_jobs(env.state, patching)
        env.state.elapsed_steps += 1
    env.start_action("A", "reconnect", "A1")
    advance_defender_jobs(env.state, patching)
    env.state.elapsed_steps += 1
    assert env.start_attacks() == {}
    assert not env.state.hosts["A1"].compromised
    assert not env.state.hosts["A1"].vulnerable
    assert env.state.hosts["B1"].compromised


def test_completion_uses_configured_pairing_without_mutating_settings():
    config = read_world_config(TEST_WORLD / "world_config.toml")
    config["network"]["server_pairs"] = [["A1", "B3"], ["A2", "B2"], ["A3", "B1"]]
    before = deepcopy(config)
    state = create_initial_state(config)
    start_attack_jobs(state, config, {"spread": {"duration_steps": 1}})
    assert advance_attack_jobs(state, config) == {"A1": "succeeded"}
    assert state.hosts["B3"].compromised
    assert not state.hosts["B1"].compromised
    assert config == before


@pytest.mark.parametrize(
    "source,job,error",
    [
        (7, AttackJob("B3", 2), TypeError),
        ("missing", AttackJob("B3", 2), ValueError),
        ("EA", AttackJob("B3", 2), ValueError),
        ("A3", None, TypeError),
        ("A3", DefenderJob("inspect", "B3", 2), TypeError),
        ("A3", AttackJob(None, 2), TypeError),
        ("A3", AttackJob("missing", 2), ValueError),
        ("A3", AttackJob("B1", 2), ValueError),
        ("A3", AttackJob("B3", True), TypeError),
        ("A3", AttackJob("B3", 1.5), TypeError),
        ("A3", AttackJob("B3", "2"), TypeError),
        ("A3", AttackJob("B3", 0), ValueError),
        ("A3", AttackJob("B3", -1), ValueError),
    ],
)
def test_corrupt_record_stops_before_any_timer_or_host_changes(source, job, error):
    env = WorldEnvironment(world_settings())
    env.state.attack_jobs["A1"] = AttackJob("B1", 1)
    env.state.attack_jobs[source] = job
    before = deepcopy(env.state)
    with pytest.raises(error):
        env.advance_attacks()
    assert env.state == before


def test_reset_clears_pending_jobs_and_other_worlds_and_old_references_are_independent():
    env = WorldEnvironment(world_settings())
    other = WorldEnvironment(world_settings())
    env.start_attacks()
    env.advance_attacks()
    old_state = env.state
    env.reset()
    assert env.advance_attacks() == {}
    assert old_state.attack_jobs["A1"].remaining_steps == 1
    assert other.state == env.state


def test_defender_stage_does_not_progress_attacks_or_clock():
    env = WorldEnvironment(world_settings())
    env.start_attacks()
    assert env.advance_defenders() == {}
    assert env.state.elapsed_steps == 0
    assert env.state.attack_jobs["A1"].remaining_steps == 2
