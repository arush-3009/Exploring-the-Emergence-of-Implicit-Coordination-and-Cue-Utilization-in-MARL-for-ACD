from copy import deepcopy

import pytest

from checks.scenario_helpers import world_settings
from world.environment import WorldEnvironment
from world.environment_interface import EnvironmentInterface


def test_free_query_tracks_job_lifecycle_without_observations_or_mutation(monkeypatch):
    env = WorldEnvironment(world_settings())

    def forbidden_observation(*args):
        pytest.fail("A status query must not build a full observation")

    monkeypatch.setattr(env, "observe", forbidden_observation)
    before = deepcopy(env.state)
    assert env.is_defender_free("A") is True
    assert env.is_defender_free("B") is True
    assert env.state == before

    env.start_action("A", "inspect", "A1")
    for _ in range(2):
        before = deepcopy(env.state)
        assert env.is_defender_free("A") is False
        assert env.is_defender_free("B") is True
        assert env.state == before
        env.advance_defenders()
    assert env.is_defender_free("A") is True
    env.start_action("A", "restore", "A1")
    assert env.is_defender_free("A") is False
    env.reset()
    assert env.is_defender_free("A") is True


@pytest.mark.parametrize("defender_id,error", [(None, TypeError), (True, TypeError),
                                              (1, TypeError), ([], TypeError),
                                              ("missing", ValueError)])
def test_free_query_rejects_invalid_defender_without_mutation(defender_id, error):
    env = WorldEnvironment(world_settings())
    before = deepcopy(env.state)
    with pytest.raises(error):
        env.is_defender_free(defender_id)
    assert env.state == before


def test_interface_builds_one_observation_per_defender_per_boundary(monkeypatch):
    env = WorldEnvironment(world_settings())
    interface = EnvironmentInterface(env)
    original_observe = env.observe
    calls = []

    def counted_observe(defender_id):
        calls.append((env.state.elapsed_steps, defender_id))
        return original_observe(defender_id)

    monkeypatch.setattr(env, "observe", counted_observe)
    result = interface.reset()
    assert calls == [(0, "A"), (0, "B")]
    assert result["defenders_to_act"] == ("A", "B")
    calls.clear()
    result = interface.step({"A": 1, "B": 0})
    assert calls == [(1, "A"), (1, "B")]
    assert result["defenders_to_act"] == ("B",)
    calls.clear()
    before = deepcopy(env.state)
    with pytest.raises(ValueError, match="Omit busy defenders"):
        interface.step({"A": 0, "B": 0})
    with pytest.raises(ValueError, match="Missing choices"):
        interface.step({})
    assert calls == []
    assert env.state == before
    result = interface.step({"B": 0})
    assert calls == [(2, "A"), (2, "B")]
    assert result["defenders_to_act"] == ("A", "B")

    for boundary in range(3, 51):
        calls.clear()
        result = interface.step({"A": 0, "B": 0})
        assert calls == [(boundary, "A"), (boundary, "B")]
    assert result["episode_finished"] is True
    assert result["defenders_to_act"] == ()
    assert env.is_defender_free("A") is True
    calls.clear()
    with pytest.raises(RuntimeError, match="Episode finished"):
        interface.step({})
    assert calls == []


def test_availability_checks_use_live_jobs_after_direct_environment_changes():
    env = WorldEnvironment(world_settings())
    interface = EnvironmentInterface(env)
    interface.reset()
    env.start_action("A", "inspect", "A1")
    result = interface.step({"B": 0})
    assert result["defenders_to_act"] == ("B",)
    result = interface.step({"B": 0})
    assert result["defenders_to_act"] == ("A", "B")
