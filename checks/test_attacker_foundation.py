from copy import deepcopy

import pytest

from attacker.attacker_config import read_attacker_config, validate_attacker_config
from checks.scenario_helpers import TEST_WORLD, world_settings
from world.environment import WorldEnvironment
from world.state import AttackJob, create_initial_state
from world.world_config import read_world_config


def test_default_settings_do_not_depend_on_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert read_attacker_config(TEST_WORLD / "attacker_config.toml") == {"spread": {"duration_steps": 2}}


@pytest.mark.parametrize("duration", [1, 2, 5])
def test_valid_config_is_not_changed(duration):
    config = {"spread": {"duration_steps": duration}}
    original = deepcopy(config)
    assert validate_attacker_config(config) is None
    assert config == original


@pytest.mark.parametrize(
    "config",
    [
        None,
        [],
        {},
        {"spread": {}, "extra": 1},
        {"spread": None},
        {"spread": []},
        {"spread": {}},
        {"spread": {"duration_step": 2}},
        {"spread": {"duration_steps": 2, "extra": 1}},
    ],
)
def test_invalid_structure_fails(config):
    with pytest.raises(ValueError):
        validate_attacker_config(config)


@pytest.mark.parametrize("duration", [0, -1, True, False, 2.0, "2", None])
def test_invalid_duration_fails(duration):
    with pytest.raises(ValueError, match="positive integer"):
        validate_attacker_config({"spread": {"duration_steps": duration}})


@pytest.mark.parametrize("contents", ["[spread]\nduration_steps = 0\n", "[spread\n"])
def test_file_errors_include_the_path_and_prevent_construction(tmp_path, contents):
    path = tmp_path / "bad_attacker.toml"
    path.write_text(contents)
    with pytest.raises(ValueError, match="bad_attacker.toml"):
        read_attacker_config(path)


def test_missing_file_is_not_silently_replaced(tmp_path):
    with pytest.raises(FileNotFoundError):
        read_attacker_config(tmp_path / "missing.toml")


def test_custom_settings_are_loaded_once_and_preserved_at_reset(tmp_path):
    path = tmp_path / "chosen_attacker.toml"
    path.write_text("[spread]\nduration_steps = 5\n")
    env = WorldEnvironment(world_settings({"attacker": read_attacker_config(path)}))
    loaded = env._attacker_config
    assert loaded == {"spread": {"duration_steps": 5}}

    path.write_text("[spread]\nduration_steps = 3\n")
    env.reset()
    assert env._attacker_config is loaded
    assert env._attacker_config["spread"]["duration_steps"] == 5
    assert WorldEnvironment(world_settings({"attacker": read_attacker_config(path)}))._attacker_config == {
        "spread": {"duration_steps": 3}
    }


def test_fresh_worlds_have_independent_empty_attack_jobs():
    config = read_world_config(TEST_WORLD / "world_config.toml")
    original = deepcopy(config)
    first = create_initial_state(config)
    second = create_initial_state(config)
    assert first.attack_jobs == second.attack_jobs == {}
    assert first.attack_jobs is not second.attack_jobs

    first.attack_jobs["A1"] = AttackJob(target="B1", remaining_steps=2)
    assert second.attack_jobs == {}
    assert first.hosts["A1"].compromised
    assert not first.hosts["B1"].compromised
    assert first.elapsed_steps == 0
    assert config == original


def test_reset_clears_attack_jobs_without_mutating_previous_state():
    env = WorldEnvironment(world_settings())
    previous = env.state
    job = AttackJob(target="B1", remaining_steps=1)
    previous.attack_jobs["A1"] = job
    previous.hosts["B1"].compromised = True
    previous.elapsed_steps = 7

    env.reset()
    assert env.state.attack_jobs == {}
    assert env.state.attack_jobs is not previous.attack_jobs
    assert env.state.elapsed_steps == 0
    assert env.state.hosts["A1"].compromised
    assert not env.state.hosts["B1"].compromised
    assert previous.attack_jobs["A1"] is job
    assert previous.elapsed_steps == 7
    assert previous.hosts["B1"].compromised


def test_defender_stage_leaves_attack_timers_and_clock_unchanged():
    env = WorldEnvironment(world_settings())
    env.state.attack_jobs["A1"] = AttackJob(target="B1", remaining_steps=1)
    env.start_action("A", "inspect", "A1")
    assert env.advance_defenders() == {}
    assert env.state.defenders["A"].job.remaining_steps == 1
    assert env.state.elapsed_steps == 0
    assert env.state.attack_jobs["A1"].remaining_steps == 1
    assert not env.state.hosts["B1"].compromised
