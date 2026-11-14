from dataclasses import asdict
from random import Random

import pytest

from attacker.intrusion import randomly_draw_intrusion
from checks.scenario_helpers import RANDOM_INTRUSION, world_settings
from episodes.runner import EpisodeRunner
from observations.schema import observation_feature_names
from policies.always_wait import AlwaysWait
from world.environment import WorldEnvironment
from world.environment_interface import EnvironmentInterface
from world.episode_script import episode_script_from_dict
from world.state import EpisodeScript, FalseWarning, Intrusion, Outage

NAMES = list(observation_feature_names(3))

WAIT = {"A": ("wait", None), "B": ("wait", None)}


def settings(base=None, clean=False, outages=None, warnings=None):
    overrides = dict(base or {})
    if clean:
        overrides["world.initial.compromised_servers"] = []
    if outages is not None:
        overrides["world.outages"] = outages
    if warnings is not None:
        overrides["observations.warnings"] = warnings
    return world_settings(overrides)


def feature(observation, slot, name):
    return observation[NAMES.index(f"server_{slot}.{name}")]


def test_without_the_tables_the_script_holds_only_the_intrusion(tmp_path):
    env = WorldEnvironment(world_settings(RANDOM_INTRUSION))
    env.set_world_rng(5)
    scripts = []
    for _ in range(25):
        env.reset()
        scripts.append(env.state.script)
    draws = Random(5)
    expected = [randomly_draw_intrusion(env.configuration_snapshot()["world"]["intrusion"], draws) for _ in range(25)]
    assert [script.intrusion for script in scripts] == expected
    assert env.state.intrusion == scripts[-1].intrusion
    for script in scripts:
        assert script.false_warnings == () and script.missed_servers == () and script.outages == ()
    assert WorldEnvironment(world_settings()).state.script == EpisodeScript()


def test_the_script_survives_the_trip_through_a_dict():
    script = EpisodeScript(intrusion=Intrusion("A2", 7), false_warnings=(FalseWarning("B1", 3),),
                           missed_servers=("A1", "B3"), outages=(Outage("B2", 10, 3),))
    assert episode_script_from_dict(asdict(script)) == script
    assert episode_script_from_dict(asdict(EpisodeScript())) == EpisodeScript()


@pytest.mark.parametrize("warnings", [
    {"false_warnings_per_episode": 1, "miss_share": 0.0},
    {"false_warnings_per_episode": -1, "miss_share": 0.0, "interval_range": [0, 40]},
    {"false_warnings_per_episode": True, "miss_share": 0.0, "interval_range": [0, 40]},
    {"false_warnings_per_episode": 1, "miss_share": 1.5, "interval_range": [0, 40]},
    {"false_warnings_per_episode": 1, "miss_share": 0.0, "interval_range": [0, 50]},
    {"false_warnings_per_episode": 1, "miss_share": 0.0, "interval_range": [5, 2]},
    {"false_warnings_per_episode": 1, "miss_share": 0.0, "interval_range": [0, 40], "extra": 1},
])
def test_bad_warning_settings_are_refused(tmp_path, warnings):
    with pytest.raises(ValueError):
        settings(warnings=warnings)


@pytest.mark.parametrize("outages", [
    {"per_episode": 1, "duration_steps": 3, "interval_range": [0, 40]},
    {"per_episode": 1, "duration_steps": 3, "interval_range": [0, 40], "servers": []},
    {"per_episode": 1, "duration_steps": 3, "interval_range": [0, 40], "servers": ["EA"]},
    {"per_episode": -1, "duration_steps": 3, "interval_range": [0, 40], "servers": ["B1"]},
    {"per_episode": 1, "duration_steps": 0, "interval_range": [0, 40], "servers": ["B1"]},
    {"per_episode": 1, "duration_steps": 3, "interval_range": [0, 50], "servers": ["B1"]},
    {"per_episode": 1, "duration_steps": 3, "interval_range": [0, 40], "servers": ["B1"], "extra": 1},
])
def test_bad_outage_settings_are_refused(tmp_path, outages):
    with pytest.raises(ValueError):
        settings(outages=outages)


def test_a_false_warning_reaches_its_zone_s_defender_about_a_clean_server(tmp_path):
    env = WorldEnvironment(settings(clean=True, warnings={
        "false_warnings_per_episode": 1, "miss_share": 0.0, "interval_range": [4, 4]}))
    [false_warning] = env.state.script.false_warnings
    assert false_warning.interval == 4 and false_warning.server in ("A1", "A2", "A3", "B1", "B2", "B3")
    zone = false_warning.server[0]
    other = "B" if zone == "A" else "A"

    deliveries = [env.step(WAIT)["monitoring_deliveries"] for _ in range(6)]
    assert all(not host.compromised for host in env.state.hosts.values() if host.has_file_service)
    assert deliveries[4] == {zone: {false_warning.server: {"received_step": 5}}, other: {}}
    assert all(deliveries[t] == {"A": {}, "B": {}} for t in (0, 1, 2, 3, 5))
    slot = ("A1", "A2", "A3", "B1", "B2", "B3").index(false_warning.server) % 3 + 1
    assert feature(env.encode_observation(zone), slot, "warning_received") == 1
    assert all(feature(env.encode_observation(other), s, "warning_received") == 0 for s in (1, 2, 3))


def test_a_missed_server_s_infection_is_never_warned_about(tmp_path):
    missed = WorldEnvironment(settings(warnings={
        "false_warnings_per_episode": 0, "miss_share": 1.0, "interval_range": [0, 40]}))
    noticed = WorldEnvironment(settings(warnings={
        "false_warnings_per_episode": 0, "miss_share": 0.0, "interval_range": [0, 40]}))
    assert set(missed.state.script.missed_servers) == {"A1", "A2", "A3", "B1", "B2", "B3"}
    assert noticed.state.script.missed_servers == ()

    for _ in range(12):
        missed_report = missed.step(WAIT)
        noticed_report = noticed.step(WAIT)
        assert missed_report["servers"] == noticed_report["servers"]
        assert missed_report["reward"] == noticed_report["reward"]
        assert missed_report["monitoring_deliveries"] == {"A": {}, "B": {}}
    assert missed.state.hosts["A1"].compromised and missed.state.hosts["B1"].compromised
    assert missed.state.defenders["A"].monitoring_warnings == {} and missed.state.defenders["B"].monitoring_warnings == {}
    assert set(noticed.state.defenders["A"].monitoring_warnings) == {"A1"}
    assert set(noticed.state.defenders["B"].monitoring_warnings) == {"B1"}


def test_an_outage_stops_the_service_fails_its_requests_and_recovers_by_itself(tmp_path):
    env = WorldEnvironment(settings(clean=True, outages={
        "per_episode": 1, "duration_steps": 3, "interval_range": [2, 2], "servers": ["B1"]}))
    assert env.state.script.outages == (Outage(server="B1", interval=2, duration=3),)

    reports = [env.step(WAIT) for _ in range(7)]
    assert [report["outages_started"] for report in reports] == [[], [], ["B1"], [], [], [], []]
    assert [report["servers"]["B1"]["service_running"] for report in reports] == [True, True, False, False, False, True, True]
    assert all(report["servers"]["B1"]["isolated"] is False for report in reports)

    def outcome(report, source, target):
        return next(r["succeeded"] for r in report["request_results"] if r["source"] == source and r["target"] == target)

    for t in (2, 3, 4):
        assert outcome(reports[t], "EB", "B1") is False
        assert outcome(reports[t], "A1", "B1") is False
        assert outcome(reports[t], "B1", "A1") is False
        assert outcome(reports[t], "EA", "A1") is True
        assert reports[t]["reward"]["failed_request_count"] == 3
    for t in (0, 1, 5, 6):
        assert reports[t]["reward"]["failed_request_count"] == 0

    env2 = WorldEnvironment(settings(clean=True, outages={
        "per_episode": 1, "duration_steps": 3, "interval_range": [2, 2], "servers": ["B1"]}))
    for _ in range(3):
        env2.step(WAIT)
    b, a = env2.encode_observation("B"), env2.encode_observation("A")
    assert feature(b, 1, "service_running") == 0 and feature(b, 1, "employee_request_result.failed") == 1
    assert feature(b, 1, "warning_received") == 0
    assert feature(a, 1, "peer_request_result.failed") == 1 and feature(a, 1, "service_running") == 1


def test_an_outage_s_end_does_not_restart_a_service_a_restore_is_still_cleaning(tmp_path):
    env = WorldEnvironment(settings(clean=True, outages={
        "per_episode": 1, "duration_steps": 2, "interval_range": [0, 0], "servers": ["B1"]}))
    commands = [WAIT,  # interval 0, the outage stops B1
                {"A": ("wait", None), "B": ("restore", "B1")},  # 1, B starts a four-interval Restore of B1
                {"A": ("wait", None)},  # 2, the outage ends while B is busy
                {"A": ("wait", None)},                      # 3
                {"A": ("wait", None)},  # 4, the Restore finishes
                WAIT]                                       # 5
    running = [env.step(command)["servers"]["B1"]["service_running"] for command in commands]
    assert running == [False, False, False, False, True, True]
    assert env.state.hosts["B1"].isolated is True


@pytest.mark.parametrize("outage_start, expected_running", [
    (0, [False, False, False, True, True, True, True, True]),
    (1, [False, False, False, False, True, True, True, True]),
    (2, [False, False, False, False, False, True, True, True]),
    (3, [False, False, False, False, False, False, True, True]),
    (4, [False, False, False, True, False, False, False, True]),
])
def test_restore_completion_keeps_an_active_outage_down(tmp_path, outage_start, expected_running):
    env = WorldEnvironment(settings(base={"actions.restore.patches_server": True}, outages={
        "per_episode": 1, "duration_steps": 3,
        "interval_range": [outage_start, outage_start], "servers": ["A1"]}))

    for interval, running in enumerate(expected_running):
        commands = {"B": ("wait", None)}
        if interval == 0:
            commands["A"] = ("restore", "A1")
        elif interval == 4:
            commands["A"] = ("reconnect", "A1")
        elif interval > 3:
            commands["A"] = ("wait", None)
        report = env.step(commands)
        host = report["servers"]["A1"]
        assert host["service_running"] is running
        assert feature(env.encode_observation("A"), 1, "service_running") == int(running)
        if interval == 3:
            assert report["defender_completions"] == {"A": "restore"}
            assert not host["compromised"] and not host["vulnerable"]
            assert host["isolated"] and env.state.defenders["A"].job is None
        if interval >= 4:
            assert not host["isolated"]
            assert report["reward"]["failed_request_count"] == (0 if running else 3)
            assert feature(env.encode_observation("B"), 1, "peer_request_result.failed") == int(not running)


@pytest.mark.parametrize("reverse_order", [False, True])
def test_an_ending_outage_cannot_override_another_active_outage(tmp_path, reverse_order):
    env = WorldEnvironment(settings(clean=True))
    outages = [Outage("B1", 1, 4), Outage("B1", 2, 2)]
    if reverse_order:
        outages.reverse()
    env.state.script = EpisodeScript(outages=tuple(outages))
    running = []
    for _ in range(7):
        report = env.step(WAIT)
        running.append(report["servers"]["B1"]["service_running"])
    assert running == [True, False, False, False, False, True, True]


def test_a_stopped_server_cannot_be_infected_by_spread_while_it_is_down(tmp_path):
    env = WorldEnvironment(settings(outages={
        "per_episode": 1, "duration_steps": 3, "interval_range": [0, 0], "servers": ["B1"]}))
    compromised = [env.step(WAIT)["servers"]["B1"]["compromised"] for _ in range(7)]
    assert compromised[:3] == [False, False, False]
    assert compromised[-1] is True


def test_turning_one_kind_of_event_on_does_not_move_the_others(tmp_path):
    warnings_one = {"false_warnings_per_episode": 1, "miss_share": 0.1, "interval_range": [0, 40]}
    warnings_two = {"false_warnings_per_episode": 2, "miss_share": 0.1, "interval_range": [0, 40]}
    outages = {"per_episode": 1, "duration_steps": 3, "interval_range": [0, 40], "servers": ["A1", "A2", "A3", "B1", "B2", "B3"]}
    worlds = {
        "intrusion only": WorldEnvironment(settings(RANDOM_INTRUSION)),
        "one false warning": WorldEnvironment(settings(RANDOM_INTRUSION, warnings=warnings_one)),
        "two false warnings and outages": WorldEnvironment(settings(RANDOM_INTRUSION, outages=outages, warnings=warnings_two)),
        "outages only": WorldEnvironment(settings(RANDOM_INTRUSION, outages=outages)),
    }
    scripts = {}
    for name, env in worlds.items():
        env.set_world_rng(11)
        scripts[name] = []
        for _ in range(30):
            env.reset()
            scripts[name].append(env.state.script)

    intrusions = {name: [s.intrusion for s in these] for name, these in scripts.items()}
    assert len({tuple(values) for values in intrusions.values()}) == 1
    assert [s.missed_servers for s in scripts["one false warning"]] == [s.missed_servers for s in scripts["two false warnings and outages"]]
    assert [s.false_warnings[0] for s in scripts["one false warning"]] == [s.false_warnings[0] for s in scripts["two false warnings and outages"]]
    assert [s.outages for s in scripts["outages only"]] == [s.outages for s in scripts["two false warnings and outages"]]
    assert len({s.false_warnings[0] for s in scripts["one false warning"]}) > 10
    assert any(s.missed_servers for s in scripts["one false warning"]) and not all(s.missed_servers for s in scripts["one false warning"])
    assert len({s.outages[0].server for s in scripts["outages only"]}) == 6
    env = worlds["two false warnings and outages"]
    env.set_world_rng(11)
    env.reset()
    assert env.state.script == scripts["two false warnings and outages"][0]


def noisy_world():
    outages = {"per_episode": 1, "duration_steps": 3, "interval_range": [0, 40], "servers": ["A1", "A2", "A3", "B1", "B2", "B3"]}
    warnings = {"false_warnings_per_episode": 1, "miss_share": 0.5, "interval_range": [0, 40]}
    return WorldEnvironment(settings(RANDOM_INTRUSION, outages=outages, warnings=warnings))


def test_the_log_carries_the_script_exactly():
    env = noisy_world()
    env.set_world_rng(3)
    policies = {"A": AlwaysWait(), "B": AlwaysWait()}
    runner = EpisodeRunner(EnvironmentInterface(env), policies)
    logs = []
    for _ in range(12):
        log = runner.run()
        logs.append(log)
        assert log.script == asdict(env.state.script)
    assert any(log.script["outages"] for log in logs) and any(log.script["missed_servers"] for log in logs)
    assert asdict(episode_script_from_dict(logs[0].script)) == logs[0].script
