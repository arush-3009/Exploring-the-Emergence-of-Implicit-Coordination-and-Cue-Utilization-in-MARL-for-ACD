from copy import deepcopy

import pytest

from checks.scenario_helpers import TEST_WORLD, world_settings
from rewards.reward_config import read_reward_config, validate_reward_config
from workload.workload_config import read_workload_config
from world.environment import WorldEnvironment

WAIT = {"A": ("wait", None), "B": ("wait", None)}


@pytest.mark.parametrize("field", ["per_compromised_server", "per_inspection"])
@pytest.mark.parametrize("value", [-1, True, "2", None, float("inf"), float("nan"), 10**400])
def test_bad_weights_raise(field, value):
    config = read_reward_config(TEST_WORLD / "reward_config.toml")
    config["penalties"][field] = value
    with pytest.raises(ValueError):
        validate_reward_config(config)


@pytest.mark.parametrize("config", [None, {}, {"penalties": {}}, {"penalties": []},
    {"penalties": {"per_compromised_server": 2, "per_failed_request": 1, "typo": 2}},
    {"penalties": {"per_compromised_server": 2, "per_failed_request": 1}, "typo": {}}])
def test_bad_structure_raises(config):
    with pytest.raises(ValueError):
        validate_reward_config(config)


def test_reader_reports_bad_file_and_is_independent_of_cwd(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert read_reward_config(TEST_WORLD / "reward_config.toml")["penalties"]["per_compromised_server"] == 2.0
    path = tmp_path / "bad.toml"
    path.write_text('[penalties]\nper_compromised_server = "bad"\nper_failed_request = 1\nper_inspection = 0\n')
    with pytest.raises(ValueError, match="Invalid reward configuration"):
        WorldEnvironment(world_settings({"rewards": read_reward_config(path)}))


def test_no_reward_before_work_and_after_reset():
    env = WorldEnvironment(world_settings())
    for _ in range(2):
        before = deepcopy(env.state)
        with pytest.raises(ValueError, match="workload results"):
            env.calculate_reward(0)
        assert env.state == before
        assert env.step(WAIT)["reward"]["shared_reward"] == -2
        env.reset()


def test_wait_counts_final_compromise_not_new_infections_or_observed_evidence():
    env = WorldEnvironment(world_settings())
    scores = [env.step(WAIT)["reward"] for _ in range(3)]
    assert [r["shared_reward"] for r in scores] == [-2, -4, -4]
    assert [r["compromised_server_count"] for r in scores] == [1, 2, 2]
    assert all(r["failed_request_count"] == 0 for r in scores)
    assert env.observe("B")["servers"]["B1"]["warning_received"] == 0


def test_restore_then_reconnect_trace_and_old_reports_stay_detached():
    env = WorldEnvironment(world_settings())
    rewards = []
    for action in ("restore", None, None, None, "reconnect"):
        commands = {"B": ("wait", None)}
        if action:
            commands["A"] = (action, "A1")
        report = env.step(commands)
        rewards.append(report["reward"])
    assert [r["shared_reward"] for r in rewards] == [-5, -5, -5, -3, 0]
    assert [r["compromised_server_count"] for r in rewards] == [1, 1, 1, 0, 0]
    assert [r["failed_request_count"] for r in rewards] == [3, 3, 3, 3, 0]
    assert env.state.elapsed_steps == 5
    assert not env.state.hosts["A1"].compromised
    assert not env.state.hosts["B1"].compromised
    before = deepcopy(env.state)
    rewards[0]["shared_reward"] = 999
    assert env.calculate_reward(0)["shared_reward"] == 0
    assert env.state == before


def test_isolation_retains_compromise_and_does_not_double_count_both_endpoints():
    env = WorldEnvironment(world_settings())
    reward = env.step({"A": ("isolate", "A1"), "B": ("isolate", "B1")})["reward"]
    assert reward == {"compromised_server_count": 1, "failed_request_count": 4,
                      "compromise_cost_by_zone": {"A": 2.0, "B": 0.0},
                      "compromise_cost": 2.0, "request_failure_cost": 4.0,
                      "inspection_start_count": 0, "inspection_cost": 0.0,
                      "shared_reward": -6.0}


def test_repeated_failed_requests_count_separately(tmp_path):
    path = tmp_path / "work.toml"
    path.write_text("[requests]\nper_route_per_interval = 3\n")
    env = WorldEnvironment(world_settings({"workload": read_workload_config(path)}))
    reward = env.step({"A": ("isolate", "A1"), "B": ("wait", None)})["reward"]
    assert reward["failed_request_count"] == 9
    assert reward["shared_reward"] == -11


def test_custom_weights_do_not_change_dynamics_or_observations_and_load_once(tmp_path):
    path = tmp_path / "reward.toml"
    path.write_text("[penalties]\nper_compromised_server = 0\nper_failed_request = 0.5\nper_inspection = 0\n")
    changed = WorldEnvironment(world_settings({"rewards": read_reward_config(path)}))
    path.write_text("[penalties]\nper_compromised_server = 99\nper_failed_request = 99\nper_inspection = 0\n")
    default = WorldEnvironment(world_settings())
    commands = {"A": ("isolate", "A1"), "B": ("wait", None)}
    first, second = default.step(commands), changed.step(commands)
    assert first.pop("reward")["shared_reward"] == -5
    assert second.pop("reward")["shared_reward"] == -1.5
    assert first == second and default.state == changed.state
    assert all(default.observe(zone) == changed.observe(zone) for zone in ("A", "B"))
    changed.reset()
    assert changed.step(commands)["reward"]["shared_reward"] == -1.5


def test_scoring_is_pure_and_reads_truth_independently_of_warnings():
    env = WorldEnvironment(world_settings())
    env.step(WAIT)
    before = deepcopy(env.state)
    assert env.calculate_reward(0) == env.calculate_reward(0)
    assert env.state == before
    observation = env.observe("A")
    env.state.hosts["A1"].compromised = False
    assert env.calculate_reward(0)["shared_reward"] == 0
    assert env.observe("A") == observation


def test_last_interval_is_scored_without_flushing_restore(tmp_path):
    env = WorldEnvironment(world_settings({"world.episode.max_steps": 1}))
    report = env.step({"A": ("restore", "A1"), "B": ("wait", None)})
    assert report["episode_finished"] and report["reward"]["shared_reward"] == -5
    assert env.state.defenders["A"].job.remaining_steps == 3
    with pytest.raises(RuntimeError):
        env.step({"B": ("wait", None)})


def test_finite_weights_that_overflow_a_score_raise(tmp_path):
    path = tmp_path / "reward.toml"
    path.write_text("[penalties]\nper_compromised_server = 1e308\nper_failed_request = 0\nper_inspection = 0\n")
    env = WorldEnvironment(world_settings({"rewards": read_reward_config(path)}))
    env.step(WAIT)
    with pytest.raises(ValueError, match="overflowed"):
        env.step(WAIT)


def test_zero_a_penalty_keeps_infection_spread_warnings_and_b_cost(tmp_path):
    changed = WorldEnvironment(world_settings({"rewards.compromise_penalties_by_zone.A": 0}))
    default = WorldEnvironment(world_settings())
    for interval in range(8):
        plain, zero_a = default.step(WAIT), changed.step(WAIT)
        old_reward, reward = plain.pop("reward"), zero_a.pop("reward")
        assert plain == zero_a and default.state == changed.state
        assert default.encode_observation("A").tolist() == changed.encode_observation("A").tolist()
        assert default.encode_observation("B").tolist() == changed.encode_observation("B").tolist()
        assert reward["compromised_server_count"] == (1 if interval == 0 else 2)
        assert reward["compromise_cost_by_zone"] == {"A": 0, "B": 0 if interval == 0 else 2}
        assert reward["shared_reward"] == old_reward["shared_reward"] + 2
    assert changed.observe("A")["servers"]["A1"]["warning_received"] == 1


@pytest.mark.parametrize("override", ['C = 0', 'A = -1', 'A = true', 'A = nan', 'A = "0"'])
def test_bad_zone_penalty_cannot_silently_change_the_experiment(tmp_path, override):
    path = tmp_path / "reward.toml"
    path.write_text((TEST_WORLD / "reward_config.toml").read_text()
                    + '\n[compromise_penalties_by_zone]\n' + override + '\n')
    with pytest.raises(ValueError):
        WorldEnvironment(world_settings({"rewards": read_reward_config(path)}))
