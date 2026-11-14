from copy import deepcopy

import pytest

from checks.scenario_helpers import TEST_WORLD, world_settings
from world.environment import WorldEnvironment
from world.state import DefenderJob, create_initial_state
from world.world_config import read_world_config, validate_world_config


@pytest.mark.parametrize("zone_names", [("A", "B"), ("East", "West")])
def test_initial_defenders_are_free_and_follow_configured_zones(zone_names):
    config = read_world_config(TEST_WORLD / "world_config.toml")
    original_zones = list(config["zones"].values())
    config["zones"] = dict(zip(zone_names, original_zones, strict=True))
    validate_world_config(config)
    state = create_initial_state(config)

    assert set(state.defenders) == set(zone_names)
    assert all(defender.job is None for defender in state.defenders.values())
    assert state.defenders[zone_names[0]] is not state.defenders[zone_names[1]]
    assert set(state.hosts) == {"EA", "A1", "A2", "A3", "EB", "B1", "B2", "B3"}


def test_defender_records_are_independent_between_zones_and_worlds():
    config = read_world_config(TEST_WORLD / "world_config.toml")
    original_config = deepcopy(config)
    first = create_initial_state(config)
    second = create_initial_state(config)
    first.defenders["A"].job = DefenderJob(
        action="inspect", target="A2", remaining_steps=1
    )

    assert first.defenders["B"].job is None
    assert all(defender.job is None for defender in second.defenders.values())
    assert first.defenders["A"] is not second.defenders["A"]
    assert config == original_config


def test_reset_discards_both_jobs_without_mutating_the_previous_state():
    env = WorldEnvironment(world_settings())
    previous = env.state
    previous.defenders["A"].job = DefenderJob(
        action="restore", target="A1", remaining_steps=3
    )
    previous.defenders["B"].job = DefenderJob(
        action="inspect", target="B2", remaining_steps=1
    )
    previous.elapsed_steps = 1

    env.reset()

    assert set(env.state.defenders) == {"A", "B"}
    assert all(defender.job is None for defender in env.state.defenders.values())
    assert env.state.elapsed_steps == 0
    for zone_id in ("A", "B"):
        assert env.state.defenders[zone_id] is not previous.defenders[zone_id]
    assert previous.defenders["A"].job.remaining_steps == 3
    assert previous.defenders["B"].job.remaining_steps == 1
    assert previous.elapsed_steps == 1
