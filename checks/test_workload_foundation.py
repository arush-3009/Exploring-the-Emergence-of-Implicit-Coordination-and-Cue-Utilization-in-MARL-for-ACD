from collections import Counter
from copy import deepcopy

import pytest

from checks.scenario_helpers import TEST_WORLD
from workload.file_requests import build_required_requests
from workload.workload_config import read_workload_config, validate_workload_config
from world.world_config import read_world_config, validate_world_config

EXPECTED_ROUTES = [
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


def test_defaults_and_builder_work_outside_repo(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    settings = read_workload_config(TEST_WORLD / "workload_config.toml")
    assert settings == {"requests": {"per_route_per_interval": 1}}
    requests = build_required_requests(read_world_config(TEST_WORLD / "world_config.toml"), settings)
    assert requests == EXPECTED_ROUTES
    assert len(requests) == len(set(requests)) == 12


@pytest.mark.parametrize("count", [1, 2, 3])
def test_each_route_gets_configured_number_of_separate_operations(count):
    settings = {"requests": {"per_route_per_interval": count}}
    before = deepcopy(settings)
    validate_workload_config(settings)
    requests = build_required_requests(read_world_config(TEST_WORLD / "world_config.toml"), settings)
    assert Counter(requests) == {route: count for route in EXPECTED_ROUTES}
    assert len(requests) == 12 * count
    assert settings == before


@pytest.mark.parametrize(
    "config",
    [
        None,
        [],
        {},
        {"requests": {}, "extra": 1},
        {"requests": None},
        {"requests": []},
        {"requests": {}},
        {"requests": {"per_route": 1}},
        {"requests": {"per_route_per_interval": 1, "extra": 1}},
    ],
)
def test_invalid_structure_fails(config):
    with pytest.raises(ValueError):
        validate_workload_config(config)


@pytest.mark.parametrize("count", [0, -1, True, False, 1.0, "1", None])
def test_invalid_request_count_fails(count):
    with pytest.raises(ValueError, match="positive integer"):
        validate_workload_config({"requests": {"per_route_per_interval": count}})


@pytest.mark.parametrize(
    "contents", ["[requests\n", "[requests]\nper_route_per_interval = 0\n"]
)
def test_bad_file_reports_its_path(tmp_path, contents):
    path = tmp_path / "bad_workload.toml"
    path.write_text(contents)
    with pytest.raises(ValueError, match="bad_workload.toml"):
        read_workload_config(path)


def test_explicit_file_and_missing_file(tmp_path):
    path = tmp_path / "custom_workload.toml"
    path.write_text("[requests]\nper_route_per_interval = 2\n")
    assert (
        len(build_required_requests(read_world_config(TEST_WORLD / "world_config.toml"), read_workload_config(path)))
        == 24
    )
    with pytest.raises(FileNotFoundError):
        read_workload_config(tmp_path / "missing.toml")


def test_host_renaming_and_pair_changes_are_derived_from_world():
    world = read_world_config(TEST_WORLD / "world_config.toml")
    world["zones"]["A"]["employee"] = "worker"
    world["zones"]["A"]["servers"][0] = "archive"
    world["initial"]["compromised_servers"] = ["archive"]
    world["servers"]["vulnerable_servers"][0] = "archive"
    world["network"]["server_pairs"] = [["archive", "B3"], ["A2", "B2"], ["A3", "B1"]]
    validate_world_config(world)
    requests = build_required_requests(world, read_workload_config(TEST_WORLD / "workload_config.toml"))
    assert requests == [
        ("worker", "archive"),
        ("worker", "A2"),
        ("worker", "A3"),
        ("EB", "B1"),
        ("EB", "B2"),
        ("EB", "B3"),
        ("archive", "B3"),
        ("B3", "archive"),
        ("A2", "B2"),
        ("B2", "A2"),
        ("A3", "B1"),
        ("B1", "A3"),
    ]


def test_blocked_and_compromised_servers_do_not_erase_demand():
    world = read_world_config(TEST_WORLD / "world_config.toml")
    world["initial"]["isolated_servers"] = ["A1", "B1"]
    world["initial"]["servers_with_stopped_services"] = ["A1", "B1"]
    world["initial"]["compromised_servers"] = ["A1", "B1"]
    validate_world_config(world)
    before = deepcopy(world)
    assert build_required_requests(world, read_workload_config(TEST_WORLD / "workload_config.toml")) == EXPECTED_ROUTES
    assert world == before


def test_returned_lists_are_independent():
    world, workload = read_world_config(TEST_WORLD / "world_config.toml"), read_workload_config(TEST_WORLD / "workload_config.toml")
    first = build_required_requests(world, workload)
    second = build_required_requests(world, workload)
    first.clear()
    assert second == EXPECTED_ROUTES
