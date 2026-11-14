import shutil
from pathlib import Path

import pytest

from checks.scenario_helpers import TEST_WORLD, world_settings
from studies.definitions import WORLDS
from world.environment import WorldEnvironment
from world.settings import SETTINGS_FILES, apply_overrides, load_world_settings

ROOT = Path(__file__).resolve().parents[1]


def test_the_environment_keeps_exactly_the_settings_it_was_built_from():
    settings = load_world_settings(TEST_WORLD)
    environment = WorldEnvironment(settings)
    assert environment.configuration_snapshot() == settings
    settings["world"]["episode"]["max_steps"] = 3
    assert environment.configuration_snapshot()["world"]["episode"]["max_steps"] == 50


def test_a_copied_world_folder_gives_the_same_settings(tmp_path):
    shutil.copytree(TEST_WORLD, tmp_path / "copy")
    assert load_world_settings(tmp_path / "copy") == load_world_settings(TEST_WORLD)


def test_an_override_changes_only_its_own_component():
    defaults = world_settings()
    settings = world_settings({"world.initial.compromised_servers": ["B1"]})
    assert settings["world"]["initial"]["compromised_servers"] == ["B1"]
    for component in ("actions", "attacker", "workload", "observations", "rewards"):
        assert settings[component] == defaults[component]
    assert apply_overrides(defaults, {}) == defaults


def test_a_misspelled_extra_or_missing_file_and_a_missing_folder_are_rejected(tmp_path):
    folder = tmp_path / "typo"
    shutil.copytree(TEST_WORLD, folder)
    (folder / "world_config.toml").rename(folder / "world_conifg.toml")
    with pytest.raises(ValueError, match="world_conifg.toml"):
        load_world_settings(folder)
    shutil.copytree(TEST_WORLD, tmp_path / "extra")
    shutil.copy(ROOT / "studies/settings/training_config.toml", tmp_path / "extra")
    with pytest.raises(ValueError, match="training_config.toml"):
        load_world_settings(tmp_path / "extra")
    with pytest.raises(ValueError, match="must hold exactly"):
        load_world_settings(tmp_path / "not-there")


def test_the_five_worlds_differ_only_in_their_warning_and_outage_settings():
    reference = load_world_settings(ROOT / "worlds" / "reliable-warnings")
    folders = []
    for path in (ROOT / "worlds").iterdir():
        if path.is_dir():
            folders.append(path.name)
    assert sorted(folders) == sorted(WORLDS)
    for world in WORLDS:
        settings = load_world_settings(ROOT / "worlds" / world)
        assert set(settings) == set(SETTINGS_FILES)
        for component in ("actions", "attacker", "workload", "rewards"):
            assert settings[component] == reference[component]
        assert {**settings["world"], "outages": None} == {**reference["world"], "outages": None}
        assert {**settings["observations"], "warnings": None} == {**reference["observations"], "warnings": None}
    outages = load_world_settings(ROOT / "worlds" / "one-false-warning-missed-warnings-outages")["world"]["outages"]
    assert outages["per_episode"] == 1 and outages["duration_steps"] == 3
