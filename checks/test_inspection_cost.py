import pytest

from checks.scenario_helpers import TEST_WORLD, world_settings
from rewards.reward_config import read_reward_config, validate_reward_config
from world.environment import WorldEnvironment


def with_inspection_cost(cost, overrides=None):
    return world_settings({**(overrides or {}), "rewards.penalties.per_inspection": cost})


@pytest.mark.parametrize("cost", [0, 0.5, 1])
def test_both_starts_charge_once_rejection_and_completion_do_not_charge(tmp_path, cost):
    env = WorldEnvironment(with_inspection_cost(cost))
    commands = {"A": ("inspect", "A1"), "B": ("inspect", "B2")}
    start = env.step(commands)
    assert start["reward"]["inspection_start_count"] == 2
    assert start["reward"]["inspection_cost"] == 2 * cost
    assert start["reward"]["shared_reward"] == -2 - 2 * cost
    end = env.step(commands)
    assert end["defender_command_results"] == {"A": "rejected", "B": "rejected"}
    assert end["defender_completions"] == {"A": "inspect", "B": "inspect"}
    assert end["reward"]["inspection_start_count"] == end["reward"]["inspection_cost"] == 0
    assert end["reward"]["shared_reward"] == -4
    wait = env.step({"A": ("wait", None), "B": ("wait", None)})
    assert wait["reward"]["inspection_start_count"] == wait["reward"]["inspection_cost"] == 0
    env.reset()
    assert env.step(commands) == start


@pytest.mark.parametrize("duration", [1, 2, 4])
def test_start_in_last_interval_is_charged_even_if_job_cannot_finish(tmp_path, duration):
    env = WorldEnvironment(with_inspection_cost(0.5, {"world.episode.max_steps": 1,
                                                      "actions.duration_steps.inspect": duration}))
    result = env.step({"A": ("inspect", "A2"), "B": ("wait", None)})
    assert result["episode_finished"]
    assert result["reward"]["inspection_start_count"] == 1
    assert result["reward"]["inspection_cost"] == 0.5
    assert ("A" in result["defender_completions"]) == (duration == 1)


def test_cost_changes_reward_but_not_truth_observations_or_inspection_accuracy(tmp_path):
    free = WorldEnvironment(world_settings())
    paid = WorldEnvironment(with_inspection_cost(1))
    schedule = ({"A": ("inspect", "A1"), "B": ("inspect", "B2")}, {},
                {"A": ("restore", "A1"), "B": ("wait", None)})
    for commands in schedule:
        first, second = free.step(commands), paid.step(commands)
        reward0, reward1 = first.pop("reward"), second.pop("reward")
        assert first == second and free.state == paid.state
        assert reward1["shared_reward"] == reward0["shared_reward"] - reward1["inspection_start_count"]
        for defender in ("A", "B"):
            assert free.observe(defender) == paid.observe(defender)


def test_inspection_setting_is_required():
    config = read_reward_config(TEST_WORLD / "reward_config.toml")
    del config["penalties"]["per_inspection"]
    with pytest.raises(ValueError, match="per_inspection"):
        validate_reward_config(config)
