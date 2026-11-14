from copy import deepcopy

import pytest

from attacker.attacker_config import read_attacker_config
from attacker.scripted_attacker import start_attack_jobs
from checks.scenario_helpers import TEST_WORLD, world_settings
from world.environment import WorldEnvironment
from world.state import AttackJob, create_initial_state
from world.world_config import read_world_config, validate_world_config


def test_default_start_creates_only_a1_to_b1_without_other_state_changes():
    env = WorldEnvironment(world_settings())
    before = deepcopy(env.state)
    assert env.start_attacks() == {"A1": "B1"}
    assert env.state.attack_jobs == {"A1": AttackJob("B1", 2)}
    before.attack_jobs = deepcopy(env.state.attack_jobs)
    assert env.state == before
    assert not env.state.hosts["B1"].compromised


@pytest.mark.parametrize(
    "host,field,value",
    [
        ("A1", "compromised", False),
        ("A1", "isolated", True),
        ("B1", "compromised", True),
        ("B1", "isolated", True),
        ("B1", "has_file_service", False),
        ("B1", "file_service_running", False),
        ("B1", "vulnerable", False),
    ],
)
def test_ineligible_conditions_skip_without_mutation(host, field, value):
    env = WorldEnvironment(world_settings())
    setattr(env.state.hosts[host], field, value)
    before = deepcopy(env.state)
    assert env.start_attacks() == {}
    assert env.state == before


def test_repeat_call_preserves_existing_job_identity_and_partial_timer():
    env = WorldEnvironment(world_settings())
    env.start_attacks()
    job = env.state.attack_jobs["A1"]
    job.remaining_steps = 1
    before = deepcopy(env.state)
    assert env.start_attacks() == {}
    assert env.state.attack_jobs["A1"] is job
    assert env.state == before


def test_existing_job_is_preserved_when_current_host_conditions_change():
    env = WorldEnvironment(world_settings())
    env.start_attacks()
    env.state.hosts["A1"].compromised = False
    env.state.hosts["B1"].isolated = True
    before = deepcopy(env.state)
    assert env.start_attacks() == {}
    assert env.state == before


def test_pair_supports_reverse_direction():
    env = WorldEnvironment(world_settings())
    env.state.hosts["A1"].compromised = False
    env.state.hosts["B1"].compromised = True
    assert env.start_attacks() == {"B1": "A1"}
    assert env.state.attack_jobs == {"B1": AttackJob("A1", 2)}


def test_independent_sources_can_start_together_without_spreading_immediately():
    env = WorldEnvironment(world_settings())
    env.state.hosts["B2"].compromised = True
    assert env.start_attacks() == {"A1": "B1", "B2": "A2"}
    assert set(env.state.attack_jobs) == {"A1", "B2"}
    assert {key for key, host in env.state.hosts.items() if host.compromised} == {
        "A1",
        "B2",
    }


def test_source_need_not_be_vulnerable_or_run_the_targeted_service():
    env = WorldEnvironment(world_settings())
    env.state.hosts["A1"].vulnerable = False
    env.state.hosts["A1"].file_service_running = False
    assert env.start_attacks() == {"A1": "B1"}


def test_pairing_is_read_from_configuration_and_settings_are_not_mutated():
    config = read_world_config(TEST_WORLD / "world_config.toml")
    config["network"]["server_pairs"] = [["B3", "A1"], ["A2", "B2"], ["B1", "A3"]]
    validate_world_config(config)
    attacker = read_attacker_config(TEST_WORLD / "attacker_config.toml")
    originals = deepcopy((config, attacker))
    state = create_initial_state(config)
    assert start_attack_jobs(state, config, attacker) == {"A1": "B3"}
    assert (config, attacker) == originals


def test_custom_loaded_duration_is_used_for_new_jobs(tmp_path):
    path = tmp_path / "attack.toml"
    path.write_text("[spread]\nduration_steps = 5\n")
    env = WorldEnvironment(world_settings({"attacker": read_attacker_config(path)}))
    path.write_text("[spread]\nduration_steps = 1\n")
    assert env.start_attacks() == {"A1": "B1"}
    assert env.state.attack_jobs["A1"].remaining_steps == 5


def test_reset_allows_a_fresh_attempt_and_other_environments_stay_independent():
    env = WorldEnvironment(world_settings())
    other = WorldEnvironment(world_settings())
    env.start_attacks()
    previous_job = env.state.attack_jobs["A1"]
    assert other.state.attack_jobs == {}
    env.reset()
    assert env.start_attacks() == {"A1": "B1"}
    assert env.state.attack_jobs["A1"] is not previous_job


def test_result_dictionary_is_not_live_state():
    env = WorldEnvironment(world_settings())
    result = env.start_attacks()
    result["A1"] = "B3"
    assert env.state.attack_jobs["A1"].target == "B1"


@pytest.mark.parametrize(
    "source,job,error",
    [
        (7, AttackJob("B3", 2), TypeError),
        ("missing", AttackJob("B3", 2), ValueError),
        ("EA", AttackJob("B3", 2), ValueError),
        ("A3", None, TypeError),
        ("A3", AttackJob(None, 2), TypeError),
        ("A3", AttackJob("missing", 2), ValueError),
        ("A3", AttackJob("B1", 2), ValueError),
        ("A3", AttackJob("B3", True), TypeError),
        ("A3", AttackJob("B3", 1.5), TypeError),
        ("A3", AttackJob("B3", "2"), TypeError),
        ("A3", AttackJob("B3", 0), ValueError),
        ("A3", AttackJob("B3", -1), ValueError),
    ],
)
def test_corrupt_existing_jobs_fail_before_any_new_job_is_created(source, job, error):
    env = WorldEnvironment(world_settings())
    env.state.attack_jobs[source] = job
    before = deepcopy(env.state)
    with pytest.raises(error):
        env.start_attacks()
    assert env.state == before
