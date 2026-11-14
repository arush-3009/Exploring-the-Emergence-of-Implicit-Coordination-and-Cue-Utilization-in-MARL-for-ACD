from copy import deepcopy

import pytest

from actions.action_config import read_action_config, validate_action_config
from checks.scenario_helpers import TEST_WORLD, world_settings
from world.environment import WorldEnvironment


@pytest.mark.parametrize(
    ("action", "duration", "starts_isolated", "ends_isolated", "ends_running"),
    [
        ("inspect", 2, False, False, True),
        ("isolate", 1, False, False, True),
        ("restore", 4, False, True, False),
        ("reconnect", 1, True, True, True),
    ],
)
def test_start_creates_the_job_and_only_applies_immediate_effects(
    action, duration, starts_isolated, ends_isolated, ends_running
):
    env = WorldEnvironment(world_settings())
    env.state.hosts["A1"].isolated = starts_isolated
    result = env.start_action("A", action, "A1")

    assert result == "accepted"
    job = env.state.defenders["A"].job
    assert (job.action, job.target, job.remaining_steps) == (action, "A1", duration)
    assert env.state.hosts["A1"].isolated == ends_isolated
    assert env.state.hosts["A1"].file_service_running == ends_running
    assert env.state.hosts["A1"].compromised
    assert env.state.defenders["B"].job is None
    assert env.state.elapsed_steps == 0


@pytest.mark.parametrize(
    "action", ["wait", "inspect", "isolate", "restore", "reconnect"]
)
def test_busy_rejection_preserves_existing_job_and_world(action):
    env = WorldEnvironment(world_settings())
    assert env.start_action("A", "inspect", "A2") == "accepted"
    before = deepcopy(env.state)
    job = env.state.defenders["A"].job
    result = env.start_action("A", action, None if action == "wait" else "A1")

    assert result == "rejected"
    assert env.state == before
    assert env.state.defenders["A"].job is job


@pytest.mark.parametrize("defender_id", [None, 7, ["A"], True])
def test_wrong_defender_id_type_raises_without_changing_state(defender_id):
    env = WorldEnvironment(world_settings())
    env.start_action("A", "inspect", "A2")
    before = deepcopy(env.state)
    with pytest.raises(TypeError, match="defender_id must be a string"):
        env.start_action(defender_id, "restore", "A1")
    assert env.state == before


@pytest.mark.parametrize("defender_id", ["missing", ""])
def test_unknown_defender_id_raises_without_changing_state(defender_id):
    env = WorldEnvironment(world_settings())
    env.start_action("A", "inspect", "A2")
    before = deepcopy(env.state)
    with pytest.raises(ValueError, match="Unknown defender_id"):
        env.start_action(defender_id, "restore", "A1")
    assert env.state == before


@pytest.mark.parametrize("busy", [False, True])
@pytest.mark.parametrize(
    ("action", "target", "error_type", "message"),
    [
        ("unknown", "A1", ValueError, "Unknown action"),
        (None, "A1", TypeError, "action must be a string"),
        (7, "A1", TypeError, "action must be a string"),
        (["inspect"], "A1", TypeError, "action must be a string"),
        ("inspect", "B1", ValueError, "belongs to zone"),
        ("inspect", "EA", ValueError, "must be a file server"),
        ("restore", "missing", ValueError, "Unknown target"),
        ("inspect", None, ValueError, "requires a target"),
        ("wait", "A1", ValueError, "does not take a target"),
        ("wait", ["A1"], TypeError, "target must be a string or None"),
        ("inspect", ["A1"], TypeError, "target must be a string or None"),
        ("inspect", 7, TypeError, "target must be a string or None"),
    ],
)
def test_invalid_commands_raise_even_while_busy_without_changing_state(
    busy, action, target, error_type, message
):
    env = WorldEnvironment(world_settings())
    if busy:
        env.start_action("A", "inspect", "A2")
    before = deepcopy(env.state)
    job = env.state.defenders["A"].job
    with pytest.raises(error_type, match=message):
        env.start_action("A", action, target)
    assert env.state == before
    assert env.state.defenders["A"].job is job


@pytest.mark.parametrize(
    ("action", "isolated"), [("isolate", True), ("reconnect", False)]
)
def test_busy_rejection_takes_precedence_over_already_satisfied(action, isolated):
    env = WorldEnvironment(world_settings())
    env.state.hosts["A1"].isolated = isolated
    env.start_action("A", "inspect", "A2")
    before = deepcopy(env.state)
    assert env.start_action("A", action, "A1") == "rejected"
    assert env.state == before


@pytest.mark.parametrize(
    ("action", "isolated"), [("isolate", True), ("reconnect", False)]
)
def test_already_satisfied_uses_public_status_and_does_not_create_work(
    action, isolated
):
    env = WorldEnvironment(world_settings())
    env.state.hosts["A1"].isolated = isolated
    before = deepcopy(env.state)
    assert env.start_action("A", action, "A1") == "already_satisfied"
    assert env.state == before


@pytest.mark.parametrize("action", ["inspect", "isolate", "restore", "reconnect"])
def test_hidden_compromise_does_not_change_command_acceptance(action):
    results = []
    jobs = []
    for compromised in (False, True):
        env = WorldEnvironment(world_settings())
        env.state.hosts["A1"].compromised = compromised
        env.state.hosts["A1"].isolated = action == "reconnect"
        results.append(env.start_action("A", action, "A1"))
        jobs.append(env.state.defenders["A"].job)
        assert env.state.hosts["A1"].compromised == compromised
    assert results == ["accepted", "accepted"]
    assert jobs[0] == jobs[1]


def test_wait_and_independent_defender_choices_do_not_advance_time_yet():
    env = WorldEnvironment(world_settings())
    before = deepcopy(env.state)
    assert env.start_action("A", "wait") == "accepted"
    assert env.state == before
    assert env.start_action("A", "inspect", "A2") == "accepted"
    assert env.start_action("B", "inspect", "B2") == "accepted"
    assert env.state.defenders["A"].job.target == "A2"
    assert env.state.defenders["B"].job.target == "B2"
    assert env.state.elapsed_steps == 0


def test_administration_still_works_on_isolated_stopped_clean_server_and_reset_clears_it():
    env = WorldEnvironment(world_settings())
    host = env.state.hosts["A2"]
    host.isolated = True
    host.file_service_running = False
    assert env.start_action("A", "restore", "A2") == "accepted"
    assert not host.compromised
    env.reset()
    assert env.state.defenders["A"].job is None
    assert not env.state.hosts["A2"].isolated
    assert env.state.hosts["A2"].file_service_running


def test_edited_duration_drives_jobs_and_stays_fixed_for_existing_environment(tmp_path):
    source = TEST_WORLD / "action_config.toml"
    selected = tmp_path / "actions.toml"
    original = source.read_text()
    selected.write_text(original.replace("inspect = 2", "inspect = 5"))
    env = WorldEnvironment(world_settings({"actions": read_action_config(selected)}))
    selected.write_text(original)
    assert env.start_action("A", "inspect", "A1") == "accepted"
    assert env.state.defenders["A"].job.remaining_steps == 5
    env.reset()
    assert env.start_action("A", "inspect", "A1") == "accepted"
    assert env.state.defenders["A"].job.remaining_steps == 5
    new_env = WorldEnvironment(world_settings({"actions": read_action_config(selected)}))
    assert new_env.start_action("A", "inspect", "A1") == "accepted"
    assert new_env.state.defenders["A"].job.remaining_steps == 2


@pytest.mark.parametrize("duration", [True, 0, -1, 1.5, "2"])
def test_invalid_durations_fail(duration):
    config = read_action_config(TEST_WORLD / "action_config.toml")
    config["duration_steps"]["inspect"] = duration
    with pytest.raises(ValueError, match="duration_steps.inspect"):
        validate_action_config(config)


@pytest.mark.parametrize(
    "config",
    [
        {},
        {"durations": {}},
        {"duration_steps": [], "restore": {"patches_server": False}},
        {"duration_steps": {"inspect": 2}, "restore": {"patches_server": False}},
        {
            "duration_steps": {
                "inspect": 2,
                "isolate": 1,
                "restore": 4,
                "reconnect": 1,
                "wait": 1,
            },
            "restore": {"patches_server": False},
        },
    ],
)
def test_incomplete_or_unknown_action_settings_fail(config):
    with pytest.raises(ValueError):
        validate_action_config(config)


def test_the_default_restore_does_not_patch():
    assert read_action_config(TEST_WORLD / "action_config.toml")["restore"] == {"patches_server": False}


@pytest.mark.parametrize(
    "restore",
    [None, [], {}, {"patches_server": 1}, {"patches_server": "true"}, {"patches_server": True, "extra": 1}],
)
def test_the_restore_setting_must_be_one_true_or_false_value(restore):
    config = read_action_config(TEST_WORLD / "action_config.toml")
    if restore is None:
        del config["restore"]
    else:
        config["restore"] = restore
    with pytest.raises(ValueError, match="restore"):
        validate_action_config(config)


def test_action_reader_finds_default_file_outside_repo_and_reports_invalid_file(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    config = read_action_config(TEST_WORLD / "action_config.toml")
    before = deepcopy(config)
    validate_action_config(config)
    assert config == before
    bad_file = tmp_path / "bad-actions.toml"
    bad_file.write_text(
        "[duration_steps]\ninspect = 0\nisolate = 1\nrestore = 4\nreconnect = 1\n"
        "[restore]\npatches_server = false\n"
    )
    with pytest.raises(ValueError, match=r"bad-actions.toml.*duration_steps.inspect"):
        WorldEnvironment(world_settings({"actions": read_action_config(bad_file)}))
