from copy import deepcopy

import pytest

from checks.scenario_helpers import TEST_WORLD
from world.state import create_initial_state
from world.world_config import read_world_config, validate_world_config


def test_default_file_works_outside_the_repository_and_returns_fresh_data(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    config = read_world_config(TEST_WORLD / "world_config.toml")
    original = deepcopy(config)
    validate_world_config(config)
    assert config == original
    assert create_initial_state(config).hosts["A1"].compromised
    config["initial"]["compromised_servers"].clear()
    assert read_world_config(TEST_WORLD / "world_config.toml") == original


def test_explicit_file_is_read_and_errors_identify_the_file_and_setting(tmp_path):
    source = TEST_WORLD / "world_config.toml"
    edited = tmp_path / "alternate.toml"
    edited.write_text(source.read_text().replace("max_steps = 50", "max_steps = 9"))
    assert read_world_config(edited)["episode"]["max_steps"] == 9
    edited.write_text(source.read_text().replace("max_steps = 50", "max_steps = 0"))
    with pytest.raises(ValueError, match=r"alternate.toml.*episode.max_steps"):
        read_world_config(edited)
    edited.write_text("[episode")
    with pytest.raises(ValueError, match="alternate.toml"):
        read_world_config(edited)


@pytest.mark.parametrize(
    ("path", "value", "error"),
    [
        (("episode", "max_steps"), True, "positive integer"),
        (("episode", "max_steps"), 0, "positive integer"),
        (("episode", "max_steps"), -1, "positive integer"),
        (("episode", "max_steps"), 5.5, "positive integer"),
        (("episode", "max_steps"), "50", "positive integer"),
        (("episode",), {"max_step": 50}, "missing keys.*unknown keys"),
        (("episode",), [], "table"),
        (("zones",), [], "two zone tables"),
        (("zones", "C"), {}, "two zone tables"),
        (("zones", "A", "servers"), ["A1", "A2"], "three servers"),
        (("zones", "A", "servers"), ["A1", "A1", "A3"], "duplicate IDs"),
        (("zones", "A", "servers"), ["A1", "A2", "B1"], "used more than once"),
        (("zones", "A", "employee"), "A1", "used more than once"),
        (("zones", "A", "employee"), " ", "nonempty text"),
        (("zones", "A", "employee"), 12, "nonempty text"),
        (("initial", "compromised_servers"), "A1", "list of IDs"),
        (("initial", "isolated_servers"), ["missing"], "not a declared server"),
        (("initial", "servers_with_stopped_services"), ["EA"], "not a declared server"),
        (("servers", "vulnerable_servers"), ["A1", "A1"], "duplicate IDs"),
        (("network", "server_pairs"), "A1-B1", "list of pairs"),
        (("network", "server_pairs"), [["A1"]], "two distinct server IDs"),
        (("network", "server_pairs"), [["A1", "A1"]], "duplicate IDs"),
        (("network", "server_pairs"), [["A1", "A2"]], "different zones"),
        (("network", "server_pairs"), [["A1", "EA"]], "not a declared server"),
        (("network", "server_pairs"), [["A1", "B1"], ["B1", "A1"]], "another pair"),
        (("network", "server_pairs"), [["A1", "B1"], ["A2", "B2"]], "every server"),
        (("initial", "compromised_servers"), [["A1"]], "nonempty text"),
    ],
)
def test_invalid_edits_fail_before_state_construction(path, value, error):
    config = read_world_config(TEST_WORLD / "world_config.toml")
    parent = config
    for key in path[:-1]:
        parent = parent[key]
    parent[path[-1]] = value
    with pytest.raises(ValueError, match=error):
        validate_world_config(config)


def test_other_labels_pairs_and_independent_initial_conditions_are_allowed():
    config = read_world_config(TEST_WORLD / "world_config.toml")
    config["zones"]["East"] = config["zones"].pop("A")
    config["zones"]["East"]["employee"] = "employee-east"
    config["network"]["server_pairs"] = [["B2", "A1"], ["A3", "B1"], ["B3", "A2"]]
    config["servers"]["vulnerable_servers"] = []
    config["initial"]["compromised_servers"] = ["A2"]
    config["initial"]["isolated_servers"] = ["A2"]
    config["initial"]["servers_with_stopped_services"] = ["A2"]
    original = deepcopy(config)
    validate_world_config(config)
    assert config == original
    state = create_initial_state(config)
    assert state.hosts["A2"].zone == "East"
    assert state.hosts["A2"].compromised and state.hosts["A2"].isolated
    assert not state.hosts["A2"].vulnerable
    assert not state.hosts["A2"].file_service_running
