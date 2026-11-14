from copy import deepcopy
from dataclasses import FrozenInstanceError

import pytest

from checks.scenario_helpers import TEST_WORLD, world_settings
from observations.observation_config import (
    hidden_peer_request_defenders,
    read_observation_config,
    suppressed_peer_failure_defenders,
    validate_observation_config,
)
from world.environment import WorldEnvironment
from world.state import MonitoringWarning
from world.world_config import read_world_config


def settings():
    return {
        "monitoring": {
            "basic_delay_steps": 6,
            "extra_information_delay_steps": 2,
            "extra_detector_zones": ["A"],
        }
    }


def test_defaults_are_checked_against_world_and_work_outside_repo(
    tmp_path, monkeypatch
):
    world = read_world_config(TEST_WORLD / "world_config.toml")
    before = deepcopy(world)
    monkeypatch.chdir(tmp_path)
    assert read_observation_config(world, TEST_WORLD / "observation_config.toml") == settings()
    assert world == before


@pytest.mark.parametrize("zones", [[], ["A"], ["B"], ["A", "B"]])
def test_detector_coverage_variants_are_allowed_without_mutating_input(zones):
    config = settings()
    config["monitoring"]["extra_detector_zones"] = zones
    config["monitoring"]["extra_information_delay_steps"] = 9
    before = deepcopy(config)
    validate_observation_config(config, read_world_config(TEST_WORLD / "world_config.toml"))
    assert config == before


@pytest.mark.parametrize("key", ["basic_delay_steps", "extra_information_delay_steps"])
@pytest.mark.parametrize("value", [0, -1, True, 2.5, "2", None])
def test_invalid_delays_raise(key, value):
    config = settings()
    config["monitoring"][key] = value
    with pytest.raises(ValueError, match=key):
        validate_observation_config(config, read_world_config(TEST_WORLD / "world_config.toml"))


@pytest.mark.parametrize("zones", ["A", None, [1], [["A"]], ["A", "A"], ["C"]])
def test_invalid_coverage_raises(zones):
    config = settings()
    config["monitoring"]["extra_detector_zones"] = zones
    with pytest.raises(ValueError, match="extra_detector_zones"):
        validate_observation_config(config, read_world_config(TEST_WORLD / "world_config.toml"))


@pytest.mark.parametrize(
    "config", [None, [], {}, {"monitoring": []}, {"monitoring": {}}]
)
def test_wrong_structure_raises(config):
    with pytest.raises(ValueError):
        validate_observation_config(config, read_world_config(TEST_WORLD / "world_config.toml"))


@pytest.mark.parametrize("location", ["top", "monitoring", "missing"])
def test_unknown_and_missing_keys_raise(location):
    config = settings()
    if location == "top":
        config["typo"] = {}
    elif location == "monitoring":
        config["monitoring"]["delay"] = 4
    else:
        del config["monitoring"]["basic_delay_steps"]
    with pytest.raises(ValueError):
        validate_observation_config(config, read_world_config(TEST_WORLD / "world_config.toml"))


@pytest.mark.parametrize("contents", ["[broken", "[monitoring]\nbasic_delay_steps = 6"])
def test_file_errors_name_the_path_and_stop_construction(tmp_path, contents):
    path = tmp_path / "bad.toml"
    path.write_text(contents)
    with pytest.raises(ValueError, match="bad.toml"):
        WorldEnvironment(world_settings({"observations": read_observation_config(read_world_config(TEST_WORLD / "world_config.toml"), path)}))


def test_missing_file_is_not_replaced_with_defaults(tmp_path):
    with pytest.raises(FileNotFoundError):
        WorldEnvironment(world_settings({"observations": read_observation_config(read_world_config(TEST_WORLD / "world_config.toml"), tmp_path / "missing.toml")}))


def test_custom_settings_load_once_and_reset_does_not_reload(tmp_path):
    path = tmp_path / "monitoring.toml"
    contents = "[monitoring]\nbasic_delay_steps = 7\nextra_information_delay_steps = 3\nextra_detector_zones = []\n"
    path.write_text(contents)
    env = WorldEnvironment(world_settings({"observations": read_observation_config(read_world_config(TEST_WORLD / "world_config.toml"), path)}))
    assert env._observation_config["monitoring"] == {
        "basic_delay_steps": 7,
        "extra_information_delay_steps": 3,
        "extra_detector_zones": [],
    }
    path.write_text(contents.replace("= 7", "= 8"))
    env.reset()
    assert env._observation_config["monitoring"]["basic_delay_steps"] == 7
    assert (
        WorldEnvironment(world_settings({"observations": read_observation_config(read_world_config(TEST_WORLD / "world_config.toml"), path)}))._observation_config[
            "monitoring"
        ]["basic_delay_steps"]
        == 8
    )


def test_warning_dictionaries_are_private_to_records_and_reset_replaces_them():
    env, other = WorldEnvironment(world_settings()), WorldEnvironment(world_settings())
    old_state = env.state
    old_state.defenders["A"].monitoring_warnings["A1"] = MonitoringWarning(0)
    assert old_state.defenders["B"].monitoring_warnings == {}
    assert other.state.defenders["A"].monitoring_warnings == {}
    env.reset()
    assert env.state.defenders["A"].monitoring_warnings == {}
    assert env.state.defenders["B"].monitoring_warnings == {}
    assert old_state.defenders["A"].monitoring_warnings == {"A1": MonitoringWarning(0)}


def test_restore_retires_the_open_warning_but_does_not_mutate_the_old_record():
    env = WorldEnvironment(world_settings())
    for _ in range(2):
        env.step({"A": ("wait", None), "B": ("wait", None)})
    delivered = env.state.defenders["A"].monitoring_warnings["A1"]
    with pytest.raises(FrozenInstanceError):
        delivered.received_step = 1
    env.step({"A": ("restore", "A1"), "B": ("wait", None)})
    while env.state.defenders["A"].job is not None:
        assert env.state.defenders["A"].monitoring_warnings["A1"] == delivered
        env.step({"B": ("wait", None)})
    assert env.state.hosts["A1"].compromised is False
    assert env.state.defenders["A"].monitoring_warnings == {}
    assert env.state.defenders["A"].inspection_findings == {}
    assert env.state.elapsed_steps - delivered.received_step == 4


def test_monitoring_adds_delivery_bookkeeping_but_not_actor_observations():
    env = WorldEnvironment(world_settings())
    for _ in range(7):
        report = env.step({"A": ("wait", None), "B": ("wait", None)})
    assert env.state.elapsed_steps == 7
    assert env.state.hosts["A1"].compromised and env.state.hosts["B1"].compromised
    assert env.state.defenders["A"].monitoring_warnings == {"A1": MonitoringWarning(6)}
    assert env.state.defenders["B"].monitoring_warnings == {}
    assert set(report) == {
        "elapsed_steps",
        "intrusion",
        "outages_started",
        "defender_command_results",
        "target_states_at_start",
        "defender_completions",
        "attacks_started",
        "attack_completions",
        "request_results",
        "monitoring_deliveries",
        "reward",
        "servers",
        "episode_finished",
    }


def test_masks_hide_peer_request_results_for_the_named_defenders_only():
    config = settings()
    config["masks"] = {"hide_peer_request_result": ["B"]}
    before = deepcopy(config)
    validate_observation_config(config, read_world_config(TEST_WORLD / "world_config.toml"))
    assert config == before
    assert hidden_peer_request_defenders(config) == ("B",)
    assert hidden_peer_request_defenders(settings()) == ()
    config["masks"]["hide_peer_request_result"] = []
    validate_observation_config(config, read_world_config(TEST_WORLD / "world_config.toml"))
    assert hidden_peer_request_defenders(config) == ()


@pytest.mark.parametrize("masks", [
    [],
    {},
    {"hide_peer_request_result": ["A"], "typo": []},
    {"hide_peer_request_result": "A"},
    {"hide_peer_request_result": [1]},
    {"hide_peer_request_result": ["A", "A"]},
    {"hide_peer_request_result": ["C"]},
])
def test_invalid_masks_raise(masks):
    config = settings()
    config["masks"] = masks
    with pytest.raises(ValueError, match="masks"):
        validate_observation_config(config, read_world_config(TEST_WORLD / "world_config.toml"))


def test_masks_load_from_a_file_and_are_saved_with_the_world_settings(tmp_path):
    path = tmp_path / "observation_config.toml"
    path.write_text((TEST_WORLD / "observation_config.toml").read_text()
                    + '\n[masks]\nhide_peer_request_result = ["A", "B"]\n')
    env = WorldEnvironment(world_settings({"observations": read_observation_config(read_world_config(TEST_WORLD / "world_config.toml"), path)}))
    assert env.configuration_snapshot()["observations"]["masks"] == {"hide_peer_request_result": ["A", "B"]}
    assert "masks" not in WorldEnvironment(world_settings()).configuration_snapshot()["observations"]


def test_failure_suppression_is_optional_and_can_target_a_different_defender_from_hiding():
    config = settings()
    assert suppressed_peer_failure_defenders(config) == ()
    config["masks"] = {"suppress_peer_failures_when_local_available": []}
    validate_observation_config(config, read_world_config(TEST_WORLD / "world_config.toml"))
    assert suppressed_peer_failure_defenders(config) == ()
    config["masks"] = {"hide_peer_request_result": ["A"], "suppress_peer_failures_when_local_available": ["B"]}
    before = deepcopy(config)
    validate_observation_config(config, read_world_config(TEST_WORLD / "world_config.toml"))
    assert config == before
    assert suppressed_peer_failure_defenders(config) == ("B",)


@pytest.mark.parametrize("defenders", ["B", [1], ["C"], ["B", "B"]])
def test_invalid_failure_suppression_defenders_raise(defenders):
    config = settings()
    config["masks"] = {"suppress_peer_failures_when_local_available": defenders}
    with pytest.raises(ValueError, match="masks"):
        validate_observation_config(config, read_world_config(TEST_WORLD / "world_config.toml"))


def test_hiding_and_failure_suppression_cannot_target_the_same_defender():
    config = settings()
    config["masks"] = {"hide_peer_request_result": ["B"], "suppress_peer_failures_when_local_available": ["B"]}
    with pytest.raises(ValueError, match="same defender"):
        validate_observation_config(config, read_world_config(TEST_WORLD / "world_config.toml"))
