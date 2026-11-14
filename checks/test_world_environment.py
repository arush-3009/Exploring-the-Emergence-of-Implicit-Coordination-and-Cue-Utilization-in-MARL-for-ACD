import pytest

from checks.scenario_helpers import TEST_WORLD, world_settings
from world.environment import WorldEnvironment
from world.world_config import read_world_config


def test_construction_starts_the_configured_world():
    env = WorldEnvironment(world_settings())

    assert env.state.elapsed_steps == 0
    assert set(env.state.hosts) == {"EA", "A1", "A2", "A3", "EB", "B1", "B2", "B3"}
    assert {name for name, host in env.state.hosts.items() if host.compromised} == {
        "A1"
    }


def test_reset_replaces_dirty_state_without_mutating_the_previous_world():
    env = WorldEnvironment(world_settings())
    previous = env.state
    previous.hosts["A1"].compromised = False
    previous.hosts["A1"].isolated = True
    previous.hosts["A1"].file_service_running = False
    previous.elapsed_steps = 7
    del previous.hosts["B3"]

    assert env.reset() is None
    assert env.state is not previous
    assert env.state.hosts["A1"] is not previous.hosts["A1"]
    assert env.state.elapsed_steps == 0
    assert env.state.hosts["A1"].compromised
    assert not env.state.hosts["A1"].isolated
    assert env.state.hosts["A1"].file_service_running
    assert "B3" in env.state.hosts

    assert previous.elapsed_steps == 7
    assert not previous.hosts["A1"].compromised
    assert previous.hosts["A1"].isolated
    assert not previous.hosts["A1"].file_service_running
    assert "B3" not in previous.hosts


def test_separate_environments_and_repeated_resets_stay_independent():
    first = WorldEnvironment(world_settings())
    second = WorldEnvironment(world_settings())
    first.state.hosts["B2"].compromised = True

    assert not second.state.hosts["B2"].compromised
    first.reset()
    assert not first.state.hosts["B2"].compromised
    first.state.hosts["A1"].compromised = False
    first.reset()
    assert first.state.hosts["A1"].compromised
    assert second.state.hosts["A1"].compromised
    assert first.state.hosts["A1"] is not second.state.hosts["A1"]


def test_reset_reuses_loaded_settings_and_new_environment_reads_file_changes(tmp_path):
    source = TEST_WORLD / "world_config.toml"
    config_path = tmp_path / "chosen_world.toml"
    original = source.read_text()
    selected = original.replace(
        'compromised_servers = ["A1"]', 'compromised_servers = ["B2"]'
    )
    config_path.write_text(selected)
    env = WorldEnvironment(world_settings({"world": read_world_config(config_path)}))
    assert {name for name, host in env.state.hosts.items() if host.compromised} == {
        "B2"
    }

    config_path.write_text(original)
    env.state.hosts["B2"].compromised = False
    env.reset()
    assert {name for name, host in env.state.hosts.items() if host.compromised} == {
        "B2"
    }
    next_env = WorldEnvironment(world_settings({"world": read_world_config(config_path)}))
    assert {
        name for name, host in next_env.state.hosts.items() if host.compromised
    } == {"A1"}
    assert config_path.read_text() == original


def test_invalid_settings_fail_before_an_environment_is_ready(tmp_path):
    source = TEST_WORLD / "world_config.toml"
    config_path = tmp_path / "invalid_world.toml"
    config_path.write_text(
        source.read_text().replace("max_steps = 50", "max_steps = 0")
    )

    with pytest.raises(ValueError, match=r"invalid_world.toml.*episode.max_steps"):
        WorldEnvironment(world_settings({"world": read_world_config(config_path)}))
