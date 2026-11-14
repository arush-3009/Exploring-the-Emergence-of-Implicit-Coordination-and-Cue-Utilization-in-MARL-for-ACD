from copy import deepcopy
from dataclasses import asdict

import numpy as np
import pytest

from checks.scenario_helpers import world_settings
from episodes.runner import EpisodeRunner
from observations.defender_observation_encoding import ObservationEncoder
from observations.schema import observation_feature_names
from policies.always_wait import AlwaysWait
from policies.random_policy import RandomPolicy
from world.environment import WorldEnvironment
from world.environment_interface import EnvironmentInterface


def policies(env):
    return {zone: RandomPolicy(len(env.action_choices(zone)), seed)
            for zone, seed in zip(env.get_defender_ids(), (51, 72), strict=True)}


def test_step_report_does_not_share_mutable_data_with_state_or_later_steps():
    direct, control = WorldEnvironment(world_settings()), WorldEnvironment(world_settings())
    commands = {"A": ("inspect", "A1"), "B": ("wait", None)}
    received_warning = False
    for _ in range(3):
        report = direct.step(commands)
        expected = control.step(commands)
        assert report == expected
        assert direct.state == control.state
        report["request_results"][0]["source"] = "changed"
        report["request_results"][0]["succeeded"] = False
        report["request_results"].clear()
        report["defender_command_results"].clear()
        report["defender_completions"].clear()
        report["attacks_started"].clear()
        report["attack_completions"].clear()
        report["reward"]["shared_reward"] = 1000
        report["elapsed_steps"] = 1000
        report["episode_finished"] = True
        for deliveries in report["monitoring_deliveries"].values():
            for delivery in deliveries.values():
                received_warning = True
                delivery["received_step"] = 1000
            deliveries.clear()
        assert direct.state == control.state
        commands = {zone: ("wait", None) for zone in direct.get_defender_ids()
                    if direct.is_defender_free(zone)}
    assert received_warning


def test_interface_returns_boundary_data_and_world_report_after_one_world_step():
    env = WorldEnvironment(world_settings())
    result = EnvironmentInterface(env).step({"A": 2, "B": 0})
    assert env.state.elapsed_steps == 1
    assert set(result) == {"observations", "observation_facts", "defenders_to_act", "shared_reward",
                           "episode_finished", "world_report", "script"}
    assert result["defenders_to_act"] == ("A", "B")
    assert result["shared_reward"] == -5.0
    assert result["world_report"]["elapsed_steps"] == 1
    assert result["world_report"]["reward"]["shared_reward"] == -5.0


def test_setup_is_reused_but_host_conditions_are_read_each_interval(monkeypatch):
    env = WorldEnvironment(world_settings())
    def forbidden(*args, **kwargs):
        raise AssertionError("Static setup must not be rebuilt during an episode or reset")

    monkeypatch.setattr("world.environment.build_defender_action_choices", forbidden)
    monkeypatch.setattr("world.environment.build_required_requests", forbidden)
    monkeypatch.setattr("attacker.scripted_attacker.build_server_partners", forbidden)
    monkeypatch.setattr("observations.defender_observation.WorldLayout.from_config", forbidden)
    monkeypatch.setattr("observations.defender_observation_encoding.own_observation_fields", forbidden)
    interface = EnvironmentInterface(env)
    interface.reset()
    interface.step({"A": 2, "B": 0})
    assert env.observe("A")["servers"]["A1"]["isolated"] == 1
    assert env.observe("B")["servers"]["B1"]["peer_request_result"] == 0
    interface.step({"A": 4, "B": 0})
    assert env.observe("B")["servers"]["B1"]["peer_request_result"] == 1
    assert env.state.hosts["B1"].compromised
    interface.reset()
    assert not env.state.hosts["B1"].compromised
    assert env.action_choices("A")[2] == ("isolate", "A1")


def test_configuration_snapshot_and_copied_world_cannot_modify_original():
    env = WorldEnvironment(world_settings())
    snapshot = env.configuration_snapshot()
    snapshot["world"]["zones"]["A"]["servers"].reverse()
    snapshot["actions"]["duration_steps"]["restore"] = 999
    snapshot["world"]["initial"]["compromised_servers"].clear()
    copied = deepcopy(env)
    copied.step({"A": ("restore", "A1"), "B": ("wait", None)})
    assert copied.state.defenders["A"].job.remaining_steps == 3
    assert env.state.elapsed_steps == 0
    assert env.state.hosts["A1"].compromised
    env.reset()
    assert env.action_choices("A")[1] == ("inspect", "A1")
    assert env.state.hosts["A1"].compromised
    with pytest.raises(TypeError):
        env._layout.partners["A1"] = "B3"


def test_command_batch_is_validated_once_before_any_start(monkeypatch):
    import world.environment as module
    original = module.validate_defender_action
    calls = []
    env = WorldEnvironment(world_settings())
    before = deepcopy(env.state)
    def check(*args):
        assert env.state == before
        calls.append(args[2])
        return original(*args)

    monkeypatch.setattr(module, "validate_defender_action", check)
    env.step({"A": ("restore", "A1"), "B": ("wait", None)})
    assert calls == ["A", "B"]
    with pytest.raises(ValueError):
        env.start_action("A", "invalid", "A1")


def test_runner_log_matches_direct_world_steps_and_repeats_with_fresh_policies():
    first, second, direct = WorldEnvironment(world_settings()), WorldEnvironment(world_settings()), WorldEnvironment(world_settings())
    log = EpisodeRunner(EnvironmentInterface(first), policies(first)).run()
    again = EpisodeRunner(EnvironmentInterface(second), policies(second)).run()
    assert len(log.shared_rewards) == 50
    assert log.action_ids == again.action_ids
    assert log.shared_rewards == again.shared_rewards
    assert log.world_reports == again.world_reports
    assert asdict(first.state) == asdict(second.state)
    for t, action_ids in enumerate(log.action_ids):
        commands = {zone: direct.decode_action(zone, action_id)
                    for zone, action_id in action_ids.items() if action_id is not None}
        assert log.world_reports[t] == direct.step(commands)
        assert log.shared_rewards[t] == log.world_reports[t]["reward"]["shared_reward"]
    assert direct.state == first.state


def test_runner_starts_only_when_run_and_an_error_returns_no_partial_log():
    env = WorldEnvironment(world_settings())
    env.step({"A": ("wait", None), "B": ("wait", None)})
    calls = []
    def invalid_after_reset(observation):
        calls.append(float(observation[0]))
        return 0 if observation[0] == 0 else -1
    runner = EpisodeRunner(EnvironmentInterface(env), {"A": invalid_after_reset, "B": AlwaysWait()})
    assert env.state.elapsed_steps == 1 and calls == []
    with pytest.raises(ValueError):
        runner.run()
    assert env.state.elapsed_steps == 1
    assert len(calls) == 2 and calls[0] == 0 and calls[1] == pytest.approx(1 / 50)


@pytest.mark.parametrize("server_count", [1, 2, 3, 5])
def test_feature_names_and_encoder_share_layout_for_each_local_slot(server_count):
    raw = WorldEnvironment(world_settings()).observe("A")
    template = raw["servers"]["A1"]
    servers = [f"host-{index}" for index in range(server_count)]
    raw["servers"] = {server: deepcopy(template) for server in reversed(servers)}
    raw["servers"][servers[-1]]["isolated"] = 1
    raw["job_action"] = 1
    raw["job_target"] = server_count
    raw["job_remaining_steps"] = 1
    values = ObservationEncoder(servers, 50, 4).encode(raw)
    names = observation_feature_names(server_count)
    assert len(values) == len(names) == 14 + 15 * server_count
    named = dict(zip(names, values, strict=True))
    assert named[f"job_target.server_{server_count}"] == 1
    assert named[f"server_{server_count}.isolated"] == 1
    assert sum(named[f"server_{index}.isolated"] for index in range(1, server_count + 1)) == 1
    assert named["last_command_feedback.none"] == 1
    assert values.dtype == np.float32
