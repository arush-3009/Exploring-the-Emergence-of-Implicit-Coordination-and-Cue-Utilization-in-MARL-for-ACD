from copy import deepcopy

from checks.scenario_helpers import TEST_WORLD
from world.state import create_initial_state
from world.world_config import read_world_config, validate_world_config


def test_initial_world_matches_the_chosen_scenario():
    state = create_initial_state(read_world_config(TEST_WORLD / "world_config.toml"))

    assert state.elapsed_steps == 0
    assert set(state.hosts) == {"EA", "A1", "A2", "A3", "EB", "B1", "B2", "B3"}
    assert {name for name, host in state.hosts.items() if host.compromised} == {"A1"}
    assert not any(host.isolated for host in state.hosts.values())

    for zone_id, employee_id in [("A", "EA"), ("B", "EB")]:
        employee = state.hosts[employee_id]
        assert employee.zone == zone_id
        assert not employee.has_file_service
        assert not employee.file_service_running
        assert not employee.vulnerable
        for number in (1, 2, 3):
            server = state.hosts[f"{zone_id}{number}"]
            assert server.zone == zone_id
            assert server.has_file_service
            assert server.file_service_running
            assert server.vulnerable


def test_new_worlds_do_not_share_mutable_state_or_change_the_config():
    config = read_world_config(TEST_WORLD / "world_config.toml")
    original_config = deepcopy(config)
    first = create_initial_state(config)
    second = create_initial_state(config)

    first.hosts["A1"].compromised = False
    first.hosts["A1"].isolated = True
    first.hosts["A1"].file_service_running = False
    first.elapsed_steps = 7
    del first.hosts["B3"]

    assert second.hosts["A1"].compromised
    assert not second.hosts["A1"].isolated
    assert second.hosts["A1"].file_service_running
    assert second.elapsed_steps == 0
    assert "B3" in second.hosts
    assert config == original_config
    assert create_initial_state(config) == second


def test_initial_properties_can_be_selected_independently():
    config = read_world_config(TEST_WORLD / "world_config.toml")
    config["servers"]["vulnerable_servers"] = ["B2"]
    config["initial"]["compromised_servers"] = ["A2"]
    config["initial"]["isolated_servers"] = ["A2"]
    config["initial"]["servers_with_stopped_services"] = ["B2"]
    validate_world_config(config)
    state = create_initial_state(config)

    a2 = state.hosts["A2"]
    assert a2.compromised and a2.isolated and a2.file_service_running
    assert not a2.vulnerable

    b2 = state.hosts["B2"]
    assert b2.has_file_service and b2.vulnerable
    assert not b2.file_service_running
    assert not b2.compromised and not b2.isolated
