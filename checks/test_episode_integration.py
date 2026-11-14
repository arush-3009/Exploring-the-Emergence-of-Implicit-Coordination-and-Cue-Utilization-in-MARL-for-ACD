from collections import Counter
from copy import deepcopy
from random import Random

import pytest

from checks.scenario_helpers import TEST_WORLD, world_settings
from world.environment import WorldEnvironment
from world.settings import load_world_settings

WAIT = {"A": ("wait", None), "B": ("wait", None)}
ACTIONS = ("wait", "inspect", "isolate", "restore", "reconnect")


def configured(tmp_path, profile):
    if profile == "default":
        return WorldEnvironment(world_settings())
    world = (TEST_WORLD / "world_config.toml").read_text()
    if profile == "fast":
        world = world.replace("max_steps = 50", "max_steps = 17")
        durations, attack, basic, extra, coverage, repeats = (1, 1, 1, 1), 1, 1, 2, [], 3
        patches = "false"
    else:
        assert profile == "slow_rewired"
        world = world.replace("max_steps = 50", "max_steps = 61")
        world = world.replace('compromised_servers = ["A1"]', 'compromised_servers = ["A1", "A2", "B3"]')
        world = world.replace('isolated_servers = []', 'isolated_servers = ["B2"]')
        world = world.replace('servers_with_stopped_services = []', 'servers_with_stopped_services = ["A3"]')
        world = world.replace('["A1", "B1"]', '["A1", "B3"]')
        world = world.replace('["A2", "B2"]', '["A2", "B1"]')
        world = world.replace('["A3", "B3"]', '["A3", "B2"]')
        durations, attack, basic, extra, coverage, repeats = (3, 2, 5, 2), 4, 3, 3, ['"A"', '"B"'], 2
        patches = "true"
    settings = {
        "world": world,
        "action": "[duration_steps]\n" + "".join(
            f"{action} = {duration}\n" for action, duration in zip(ACTIONS[1:], durations)
        ) + f"[restore]\npatches_server = {patches}\n",
        "attacker": f"[spread]\nduration_steps = {attack}\n",
        "observation": f"[monitoring]\nbasic_delay_steps = {basic}\n"
        f"extra_information_delay_steps = {extra}\nextra_detector_zones = [{', '.join(coverage)}]\n",
        "workload": f"[requests]\nper_route_per_interval = {repeats}\n",
        "reward": "[penalties]\nper_compromised_server = 0.5\nper_failed_request = 2.5\nper_inspection = 0\n",
    }
    for name, contents in settings.items():
        (tmp_path / f"{name}_config.toml").write_text(contents)
    return WorldEnvironment(load_world_settings(tmp_path))


def choices(env, rng):
    commands = {}
    for zone in env._config["zones"]:
        observation = env.observe(zone)
        if observation["job_remaining_steps"] and rng.random() < 0.7:
            continue
        action = rng.choice(ACTIONS)
        target = None if action == "wait" else rng.choice(list(observation["servers"]))
        commands[zone] = (action, target)
    return commands


def observations(env):
    before = deepcopy(env.state)
    result = {zone: env.observe(zone) for zone in env._config["zones"]}
    assert env.state == before
    for zone, observation in result.items():
        assert observation["elapsed_steps"] == before.elapsed_steps
        assert list(observation["servers"]) == env._config["zones"][zone]["servers"]
        values = [v for k, v in observation.items() if k != "servers"]
        values += [v for server in observation["servers"].values() for v in server.values()]
        assert len(values) == 30 and all(type(v) is int for v in values)
        for server in observation["servers"].values():
            assert server["warning_age"] >= -1 and server["inspection_age"] >= -1
    return result


def check_boundary(env, report, boundary):
    state = env.state
    assert state.elapsed_steps == report["elapsed_steps"] == boundary
    assert report["episode_finished"] == (boundary == env._config["episode"]["max_steps"])
    servers = {key for key, host in state.hosts.items() if host.has_file_service}
    infected = {key for key in servers if state.hosts[key].compromised}
    assert set(state.compromise_started_steps) == infected
    assert all(0 <= stamp <= boundary for stamp in state.compromise_started_steps.values())
    assert all(not host.compromised for key, host in state.hosts.items() if key not in servers)

    routes = {(zone["employee"], host) for zone in env._config["zones"].values() for host in zone["servers"]}
    routes |= {direction for a, b in env._config["network"]["server_pairs"] for direction in [(a, b), (b, a)]}
    unavailable = {key for key in servers if state.hosts[key].isolated or not state.hosts[key].file_service_running}
    failed_routes = {route for route in routes if set(route) & unavailable}
    repeat = env._workload_config["requests"]["per_route_per_interval"]
    assert Counter((r["source"], r["target"]) for r in report["request_results"]) == Counter({r: repeat for r in routes})
    for result in report["request_results"]:
        assert result["succeeded"] == ((result["source"], result["target"]) not in failed_routes)
    reward = report["reward"]
    penalties = env._reward_config["penalties"]
    assert reward["compromised_server_count"] == len(infected)
    assert reward["failed_request_count"] == len(failed_routes) * repeat
    expected = -len(infected) * penalties["per_compromised_server"] - len(failed_routes) * repeat * penalties["per_failed_request"]
    assert reward["shared_reward"] == expected

    for zone, defender in state.defenders.items():
        if defender.job is not None:
            assert defender.job.target in env._config["zones"][zone]["servers"]
            assert defender.job.remaining_steps > 0
            if defender.job.action == "restore":
                host = state.hosts[defender.job.target]
                assert host.isolated and not host.file_service_running
        for host_id, warning in defender.monitoring_warnings.items():
            assert state.hosts[host_id].zone == zone
            assert 1 <= warning.received_step <= boundary
        for host_id, finding in defender.inspection_findings.items():
            assert state.hosts[host_id].zone == zone
            assert 1 <= finding.completed_step <= boundary
        for host_id, warning in report["monitoring_deliveries"][zone].items():
            assert host_id in infected and warning["received_step"] == boundary
            monitor = env._observation_config["monitoring"]
            delays = {monitor["basic_delay_steps"]}
            if zone in monitor["extra_detector_zones"]:
                delays.add(monitor["extra_information_delay_steps"])
            assert boundary - state.compromise_started_steps[host_id] in delays


@pytest.mark.parametrize("profile", ["default", "fast", "slow_rewired"])
@pytest.mark.parametrize("seed", range(12))
def test_mixed_complete_episode_then_exact_reset_replay(tmp_path, profile, seed):
    env = configured(tmp_path, profile)
    initial = deepcopy(env.state)
    settings = deepcopy([env._config, env._action_config, env._attacker_config,
                         env._workload_config, env._observation_config, env._reward_config])
    rng = Random(seed)
    history = []
    defender_deadlines, attack_deadlines = {}, {}
    for boundary in range(1, env._config["episode"]["max_steps"] + 1):
        commands = choices(env, rng)
        submitted = deepcopy(commands)
        report = env.step(commands)
        assert commands == submitted
        for zone, result in report["defender_command_results"].items():
            action, target = commands[zone]
            if result == "accepted" and action != "wait":
                assert zone not in defender_deadlines
                defender_deadlines[zone] = (boundary - 1 + env._action_config["duration_steps"][action], action, target)
        due = {zone: action for zone, (when, action, target) in defender_deadlines.items() if when == boundary}
        assert report["defender_completions"] == due
        for zone in due:
            del defender_deadlines[zone]
            assert env.state.defenders[zone].job is None
            assert env.observe(zone)["last_command_feedback"] == 1
        for zone, (when, action, target) in defender_deadlines.items():
            job = env.state.defenders[zone].job
            assert (job.action, job.target, job.remaining_steps) == (action, target, when - boundary)

        for source in report["attacks_started"]:
            assert source not in attack_deadlines
            attack_deadlines[source] = boundary - 1 + env._attacker_config["spread"]["duration_steps"]
        attack_due = {source for source, when in attack_deadlines.items() if when == boundary}
        assert set(report["attack_completions"]) == attack_due
        for source in attack_due:
            del attack_deadlines[source]
        assert set(env.state.attack_jobs) == set(attack_deadlines)
        for source, when in attack_deadlines.items():
            assert env.state.attack_jobs[source].remaining_steps == when - boundary

        check_boundary(env, report, boundary)
        obs = observations(env)
        history.append((submitted, report, obs, deepcopy(env.state)))

    final = deepcopy(env.state)
    with pytest.raises(RuntimeError, match="Episode finished"):
        env.step(WAIT)
    assert env.state == final
    old_state = env.state
    env.reset()
    assert env.state == initial and env.state is not old_state
    for commands, report, obs, expected_state in history:
        assert env.step(dict(reversed(list(commands.items())))) == report
        assert observations(env) == obs
        assert env.state == expected_state
    assert old_state == final
    assert [env._config, env._action_config, env._attacker_config,
            env._workload_config, env._observation_config, env._reward_config] == settings


@pytest.mark.parametrize("scenario,total,infected,failed", [
    ("wait", -198, {"A1", "B1"}, 0),
    ("restore_reconnect", -18, set(), 12),
    ("both_restore_reconnect", -34, set(), 16),
    ("clean", 0, set(), 0),
])
def test_analytical_whole_episode_totals(tmp_path, scenario, total, infected, failed):
    if scenario == "clean":
        env = WorldEnvironment(world_settings({"world.initial.compromised_servers": []}))
    else:
        env = WorldEnvironment(world_settings())
    rewards, failures = [], []
    for interval in range(50):
        commands = {zone: ("wait", None) for zone, d in env.state.defenders.items() if d.job is None}
        if scenario == "restore_reconnect" and interval in (0, 4):
            commands["A"] = ("restore" if interval == 0 else "reconnect", "A1")
        if scenario == "both_restore_reconnect" and interval in (2, 6):
            commands = {zone: ("restore" if interval == 2 else "reconnect", zone + "1") for zone in ("A", "B")}
        report = env.step(commands)
        rewards.append(report["reward"]["shared_reward"])
        failures.append(report["reward"]["failed_request_count"])
    assert sum(rewards) == total and sum(failures) == failed
    assert {key for key, host in env.state.hosts.items() if host.compromised} == infected
    assert report["episode_finished"] and env.state.elapsed_steps == 50


@pytest.mark.parametrize("reconnect,outcome,reward,warning", [
    (False, "failed", -5, 8),
    (True, "succeeded", -4, 8),
])
def test_temporary_isolation_does_not_cancel_or_restart_existing_attack(reconnect, outcome, reward, warning):
    env = WorldEnvironment(world_settings())
    first = env.step({"A": ("isolate", "A1"), "B": ("wait", None)})
    assert first["attacks_started"] == {"A1": "B1"}
    assert env.state.attack_jobs["A1"].remaining_steps == 1
    second = env.step({"A": ("reconnect", "A1") if reconnect else ("wait", None), "B": ("wait", None)})
    assert second["attacks_started"] == {}
    assert second["attack_completions"] == {"A1": outcome}
    assert second["reward"]["shared_reward"] == reward
    assert env.state.hosts["B1"].compromised is reconnect
    assert env.observe("A")["servers"]["A1"]["warning_age"] == 0
    for _ in range(6):
        env.step(WAIT)
    assert env.state.elapsed_steps == warning
    assert env.observe("B")["servers"]["B1"]["warning_received"] == int(reconnect)
    assert env.observe("B")["servers"]["B1"]["warning_age"] == (0 if reconnect else -1)


@pytest.mark.parametrize("seed", [3, 11, 29])
def test_changed_sensor_workload_and_reward_settings_do_not_change_physics(tmp_path, seed):
    base = WorldEnvironment(world_settings())
    changed = WorldEnvironment(world_settings({
        "observations.monitoring": {"basic_delay_steps": 1, "extra_information_delay_steps": 3,
                                    "extra_detector_zones": ["B"]},
        "rewards.penalties": {"per_compromised_server": 0, "per_failed_request": 0.5, "per_inspection": 0},
        "workload.requests.per_route_per_interval": 3}))
    rng = Random(seed)
    for _ in range(50):
        commands = choices(base, rng)
        first, second = base.step(commands), changed.step(commands)
        assert base.state.hosts == changed.state.hosts
        assert base.state.attack_jobs == changed.state.attack_jobs
        assert base.state.compromise_started_steps == changed.state.compromise_started_steps
        for key in ("elapsed_steps", "episode_finished", "attacks_started", "attack_completions", "defender_command_results", "defender_completions"):
            assert first[key] == second[key]
        assert second["reward"]["failed_request_count"] == 3 * first["reward"]["failed_request_count"]
        assert second["reward"]["shared_reward"] == -0.5 * second["reward"]["failed_request_count"]
        for zone in ("A", "B"):
            assert base.state.defenders[zone].job == changed.state.defenders[zone].job
            assert base.state.defenders[zone].inspection_findings == changed.state.defenders[zone].inspection_findings
            a, b = base.observe(zone), changed.observe(zone)
            for obs in (a, b):
                del obs["extra_detector_available"]
                for host in obs["servers"].values():
                    del host["warning_received"], host["warning_age"]
            assert a == b
