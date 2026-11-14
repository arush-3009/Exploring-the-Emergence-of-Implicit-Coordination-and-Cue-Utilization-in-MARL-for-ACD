import json
from random import Random

import pytest

from attacker.intrusion import randomly_draw_intrusion
from checks.scenario_helpers import RANDOM_INTRUSION, world_settings
from world.environment import WorldEnvironment

ALL_SERVERS = ["A1", "A2", "A3", "B1", "B2", "B3"]
WAIT = {"A": ("wait", None), "B": ("wait", None)}


def scenario(compromised="[]", **intrusion):
    return world_settings({"world.initial.compromised_servers": json.loads(compromised), "world.intrusion": intrusion})


def test_the_test_world_draws_nothing_and_the_random_intrusion_overrides_load(tmp_path):
    assert WorldEnvironment(world_settings()).world_seed is None
    environment = WorldEnvironment(world_settings(RANDOM_INTRUSION))
    assert environment.world_seed == 0
    assert environment.configuration_snapshot()["world"]["initial"]["compromised_servers"] == []


@pytest.mark.parametrize("change,message", [
    ({"servers": []}, "at least one server"),
    ({"servers": ["EA"]}, "not a declared server"),
    ({"servers": ["A1", "A1"]}, "duplicate"),
    ({"start_interval_range": [0, 50]}, "start_interval_range"),
    ({"start_interval_range": [5, 3]}, "start_interval_range"),
    ({"start_interval_range": [0.5, 3]}, "start_interval_range"),
    ({"clean_episode_share": 1.5}, "clean_episode_share"),
    ({"clean_episode_share": True}, "clean_episode_share"),
    ({"extra": 1}, "unknown keys"),
])
def test_invalid_intrusion_settings_are_rejected(tmp_path, change, message):
    settings = {"servers": ["A1"], "start_interval_range": [0, 30], "clean_episode_share": 0.2} | change
    with pytest.raises(ValueError, match=message):
        scenario(**settings)


def test_draws_cover_every_allowed_server_and_interval_with_the_given_clean_share():
    settings = {"servers": ["A1", "B2", "B3"], "start_interval_range": [4, 9], "clean_episode_share": 0.25}
    generator = Random(1)
    draws = [randomly_draw_intrusion(settings, generator) for _ in range(4000)]
    intrusions = [draw for draw in draws if draw is not None]

    assert {intrusion.server for intrusion in intrusions} == {"A1", "B2", "B3"}
    assert {intrusion.interval for intrusion in intrusions} == set(range(4, 10))
    assert abs(draws.count(None) / len(draws) - 0.25) < 0.03
    assert None not in [randomly_draw_intrusion(settings | {"clean_episode_share": 0}, generator) for _ in range(200)]
    assert all(randomly_draw_intrusion(settings | {"clean_episode_share": 1}, generator) is None for _ in range(200))


def test_changing_the_clean_share_changes_only_which_episodes_are_clean():
    settings = {"servers": ALL_SERVERS, "start_interval_range": [0, 30], "clean_episode_share": 0}
    never_clean = [randomly_draw_intrusion(settings, generator) for generator in [Random(7)] for _ in range(300)]
    half_clean = [randomly_draw_intrusion(settings | {"clean_episode_share": 0.5}, generator)
                  for generator in [Random(7)] for _ in range(300)]

    assert 100 < half_clean.count(None) < 200
    for always, sometimes in zip(never_clean, half_clean, strict=True):
        assert sometimes is None or sometimes == always


def test_an_intrusion_on_a1_at_interval_0_plays_exactly_like_the_starting_infection(tmp_path):
    starting = WorldEnvironment(world_settings())
    intruded = WorldEnvironment(scenario(servers=["A1"], start_interval_range=[0, 0], clean_episode_share=0))
    choices = Random(3)
    for interval in range(50):
        commands = {defender: starting.decode_action(defender, choices.randrange(13))
                    for defender in ("A", "B") if starting.is_defender_free(defender)}
        first, second = starting.step(commands), intruded.step(commands)

        assert first.pop("intrusion") is None
        assert second.pop("intrusion") == ("A1" if interval == 0 else None)
        assert first == second
        for defender in ("A", "B"):
            assert starting.observe(defender) == intruded.observe(defender)


def test_a_later_intrusion_infects_at_its_interval_and_spread_and_warnings_follow_from_there(tmp_path):
    env = WorldEnvironment(scenario(servers=["A2"], start_interval_range=[7, 7], clean_episode_share=0))
    reports = []
    for _ in range(16):
        reports.append(env.step(WAIT))
        if len(reports) <= 7:
            assert not env.state.hosts["A2"].compromised

    assert [interval for interval, report in enumerate(reports) if report["intrusion"]] == [7]
    assert reports[7]["intrusion"] == "A2" and reports[7]["attacks_started"] == {"A2": "B2"}
    received = {defender: {(host, warning["received_step"]) for report in reports
                           for host, warning in report["monitoring_deliveries"][defender].items()}
                for defender in ("A", "B")}
    assert received == {"A": {("A2", 9), ("A2", 13)}, "B": {("B2", 15)}}


def test_an_intrusion_on_an_infected_server_keeps_its_earlier_infection_start(tmp_path):
    env = WorldEnvironment(scenario(compromised='["A1"]', servers=["A1"],
                                    start_interval_range=[3, 3], clean_episode_share=0))
    reports = [env.step(WAIT) for _ in range(4)]
    assert reports[3]["intrusion"] == "A1"
    assert env.state.compromise_started_steps["A1"] == 0


def test_the_seed_decides_the_sequence_and_seeding_again_restarts_it(tmp_path):
    def sequence(env, seed):
        env.set_world_rng(seed)
        draws = []
        for _ in range(30):
            env.reset()
            draws.append(env.state.intrusion)
        return draws

    env = WorldEnvironment(world_settings(RANDOM_INTRUSION))
    first = sequence(env, 4)
    assert sequence(env, 4) == first and env.world_seed == 4
    assert sequence(WorldEnvironment(world_settings(RANDOM_INTRUSION)), 4) == first
    assert sequence(env, 5) != first
    with pytest.raises(TypeError):
        env.set_world_rng(None)  # Random(None) would seed from the clock
