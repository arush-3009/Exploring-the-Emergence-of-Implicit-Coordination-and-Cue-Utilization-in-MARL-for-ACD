from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from actions.action_config import read_action_config
from checks.scenario_helpers import TEST_WORLD, world_settings
from world.environment import WorldEnvironment


def advance_defender_interval(env):
    boundary = env.state.elapsed_steps
    completed = env.advance_defenders()
    assert env.state.elapsed_steps == boundary
    env.state.elapsed_steps += 1
    return completed


def test_inspect_completes_after_exactly_two_intervals_and_only_records_locally():
    env = WorldEnvironment(world_settings())
    env.start_action("A", "inspect", "A1")
    assert env.state.defenders["A"].inspection_findings == {}
    assert advance_defender_interval(env) == {}
    assert env.state.elapsed_steps == 1
    assert env.state.defenders["A"].job.remaining_steps == 1
    assert env.state.defenders["A"].inspection_findings == {}
    assert advance_defender_interval(env) == {"A": "inspect"}
    finding = env.state.defenders["A"].inspection_findings["A1"]
    assert (finding.compromised, finding.completed_step) == (True, 2)
    assert env.state.elapsed_steps == 2
    assert env.state.defenders["A"].job is None
    assert env.state.defenders["B"].inspection_findings == {}
    assert env.state.hosts["A1"].compromised


def test_all_jobs_advance_once_per_shared_interval():
    env = WorldEnvironment(world_settings())
    env.start_action("A", "inspect", "A1")
    env.start_action("B", "restore", "B1")
    assert advance_defender_interval(env) == {}
    assert env.state.elapsed_steps == 1
    assert env.state.defenders["A"].job.remaining_steps == 1
    assert env.state.defenders["B"].job.remaining_steps == 3
    assert advance_defender_interval(env) == {"A": "inspect"}
    assert env.state.defenders["B"].job.remaining_steps == 2
    assert advance_defender_interval(env) == {}
    assert advance_defender_interval(env) == {"B": "restore"}
    assert env.state.elapsed_steps == 4


def test_both_inspections_finishing_together_have_the_same_timestamp():
    env = WorldEnvironment(world_settings())
    env.start_action("A", "inspect", "A1")
    env.start_action("B", "inspect", "B1")
    advance_defender_interval(env)
    assert advance_defender_interval(env) == {"A": "inspect", "B": "inspect"}
    assert env.state.defenders["A"].inspection_findings["A1"].completed_step == 2
    assert env.state.defenders["B"].inspection_findings["B1"].completed_step == 2


@pytest.mark.parametrize("initial_compromise", [False, True])
def test_restore_has_delayed_cleanup_but_retains_isolation_and_vulnerability(
    initial_compromise,
):
    env = WorldEnvironment(world_settings())
    host = env.state.hosts["A1"]
    host.compromised = initial_compromise
    env.start_action("A", "restore", "A1")
    for remaining in (3, 2, 1):
        assert advance_defender_interval(env) == {}
        assert env.state.defenders["A"].job.remaining_steps == remaining
        assert host.compromised == initial_compromise
        assert not host.file_service_running
        assert host.isolated
    assert advance_defender_interval(env) == {"A": "restore"}
    assert not host.compromised
    assert host.file_service_running
    assert host.isolated
    assert host.vulnerable
    assert env.state.defenders["A"].job is None
    assert env.state.defenders["A"].inspection_findings == {}
    assert advance_defender_interval(env) == {}
    assert env.state.elapsed_steps == 5


def test_a_patching_restore_also_removes_vulnerability_until_reset(tmp_path):
    env = WorldEnvironment(world_settings({"actions.restore.patches_server": True}))
    host = env.state.hosts["A1"]
    host.compromised = True
    env.start_action("A", "restore", "A1")
    for _ in range(3):
        assert advance_defender_interval(env) == {}
        assert host.vulnerable
    assert advance_defender_interval(env) == {"A": "restore"}
    assert not host.compromised
    assert host.file_service_running
    assert host.isolated
    assert not host.vulnerable
    assert all(other.vulnerable for key, other in env.state.hosts.items() if key != "A1" and other.has_file_service)
    env.reset()
    assert env.state.hosts["A1"].vulnerable


@pytest.mark.parametrize(
    ("action", "initial_isolated", "final_isolated"),
    [("isolate", False, True), ("reconnect", True, False)],
)
def test_one_interval_actions_change_only_isolation_at_completion(
    action,
    initial_isolated,
    final_isolated,
):
    env = WorldEnvironment(world_settings())
    host = env.state.hosts["A1"]
    host.isolated = initial_isolated
    before = deepcopy(host)
    env.start_action("A", action, "A1")
    assert host == before
    assert advance_defender_interval(env) == {"A": action}
    before.isolated = final_isolated
    assert host == before
    assert env.state.defenders["A"].job is None
    assert env.state.elapsed_steps == 1


def test_inspection_reads_completion_truth_and_does_not_follow_later_host_changes():
    env = WorldEnvironment(world_settings())
    env.start_action("A", "inspect", "A2")
    advance_defender_interval(env)
    env.state.hosts["A2"].compromised = True
    advance_defender_interval(env)
    finding = env.state.defenders["A"].inspection_findings["A2"]
    assert finding.compromised
    env.state.hosts["A2"].compromised = False
    advance_defender_interval(env)
    assert finding.compromised
    assert finding.completed_step == 2
    assert env.state.elapsed_steps - finding.completed_step == 1
    with pytest.raises(FrozenInstanceError):
        finding.compromised = False


def test_restore_retires_only_its_finding_and_reinspect_records_a_new_one():
    env = WorldEnvironment(world_settings())
    for target in ("A1", "A2"):
        env.start_action("A", "inspect", target)
        advance_defender_interval(env)
        advance_defender_interval(env)
    original = env.state.defenders["A"].inspection_findings["A1"]
    other = env.state.defenders["A"].inspection_findings["A2"]
    env.start_action("A", "restore", "A1")
    for _ in range(4):
        advance_defender_interval(env)
    assert not env.state.hosts["A1"].compromised
    assert "A1" not in env.state.defenders["A"].inspection_findings
    assert original.compromised
    env.start_action("A", "inspect", "A1")
    advance_defender_interval(env)
    advance_defender_interval(env)
    latest = env.state.defenders["A"].inspection_findings["A1"]
    assert not latest.compromised
    assert latest.completed_step == 10
    assert original.compromised
    assert env.state.defenders["A"].inspection_findings["A2"] is other


def test_idle_wait_and_already_satisfied_still_allow_clock_progress_without_completion():
    env = WorldEnvironment(world_settings())
    assert env.start_action("A", "wait") == "accepted"
    assert env.start_action("B", "reconnect", "B1") == "already_satisfied"
    before_hosts = deepcopy(env.state.hosts)
    assert advance_defender_interval(env) == {}
    assert env.state.elapsed_steps == 1
    assert env.state.hosts == before_hosts
    assert advance_defender_interval(env) == {}
    assert env.state.elapsed_steps == 2


def test_reset_and_separate_worlds_do_not_share_inspection_records():
    env = WorldEnvironment(world_settings())
    another = WorldEnvironment(world_settings())
    env.start_action("A", "inspect", "A1")
    advance_defender_interval(env)
    advance_defender_interval(env)
    previous = env.state
    assert another.state.defenders["A"].inspection_findings == {}
    assert previous.defenders["B"].inspection_findings == {}
    env.reset()
    assert env.state.elapsed_steps == 0
    for defender in env.state.defenders.values():
        assert defender.inspection_findings == {}
        assert defender.job is None
    assert previous.defenders["A"].inspection_findings["A1"].compromised


def test_loaded_custom_duration_controls_completion(tmp_path):

    config = read_action_config(TEST_WORLD / "action_config.toml")
    config["duration_steps"]["inspect"] = 3
    path = tmp_path / "actions.toml"
    path.write_text(
        "[duration_steps]\n"
        + "".join(
            f"{name} = {duration}\n"
            for name, duration in config["duration_steps"].items()
        )
        + "[restore]\npatches_server = false\n"
    )
    env = WorldEnvironment(world_settings({"actions": read_action_config(path)}))
    env.start_action("A", "inspect", "A1")
    assert advance_defender_interval(env) == {}
    assert advance_defender_interval(env) == {}
    assert advance_defender_interval(env) == {"A": "inspect"}
    assert env.state.defenders["A"].inspection_findings["A1"].completed_step == 3


@pytest.mark.parametrize(
    ("attribute", "value", "error"),
    [
        ("action", "fly", ValueError),
        ("remaining_steps", 0, ValueError),
        ("remaining_steps", -1, ValueError),
        ("remaining_steps", True, TypeError),
    ],
)
def test_corrupt_job_record_fails_loudly(attribute, value, error):
    env = WorldEnvironment(world_settings())
    env.start_action("A", "inspect", "A1")
    setattr(env.state.defenders["A"].job, attribute, value)
    with pytest.raises(error):
        advance_defender_interval(env)
