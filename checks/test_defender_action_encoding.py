from copy import deepcopy
from typing import get_args

import pytest

from actions.action_config import read_action_config
from actions.defender_action_encoding import (
    TARGETED_ACTIONS,
    build_defender_action_choices,
    decode_action_choice,
)
from actions.defender_actions import ActionName
from checks.scenario_helpers import TEST_WORLD, world_settings
from world.environment import WorldEnvironment
from world.state import AttackJob
from world.world_config import read_world_config, validate_world_config


@pytest.mark.parametrize("defender_id", ["A", "B"])
def test_all_choice_ids_have_explicit_meanings(defender_id):
    env = WorldEnvironment(world_settings())
    first, second, third = (defender_id + str(i) for i in (1, 2, 3))
    expected = (
        ("wait", None),
        ("inspect", first), ("isolate", first), ("restore", first), ("reconnect", first),
        ("inspect", second), ("isolate", second), ("restore", second), ("reconnect", second),
        ("inspect", third), ("isolate", third), ("restore", third), ("reconnect", third),
    )
    assert env.action_choices(defender_id) == expected
    assert len(set(expected)) == 13
    for action_id, command in enumerate(expected):
        assert env.decode_action(defender_id, action_id) == command
    assert set(TARGETED_ACTIONS) == set(read_action_config(TEST_WORLD / "action_config.toml")["duration_steps"])
    assert {command[0] for command in expected} == set(get_args(ActionName))


@pytest.mark.parametrize("bad_id", [True, False, 1.0, "1", None, [], {}])
def test_non_integer_id_raises_without_changes(bad_id):
    env = WorldEnvironment(world_settings())
    before = deepcopy(env.state)
    with pytest.raises(TypeError, match="action_id"):
        env.decode_action("A", bad_id)
    assert env.state == before


@pytest.mark.parametrize("bad_id", [-1, -13, 13, 100])
def test_out_of_range_id_raises_instead_of_wrapping(bad_id):
    env = WorldEnvironment(world_settings())
    with pytest.raises(ValueError, match="between 0 and 12"):
        env.decode_action("A", bad_id)


@pytest.mark.parametrize("defender_id,error", [(0, TypeError), (None, TypeError),
                                                   ([], TypeError), ("C", ValueError)])
def test_both_entry_points_reject_invalid_defender(defender_id, error):
    env = WorldEnvironment(world_settings())
    with pytest.raises(error, match="defender_id"):
        env.action_choices(defender_id)
    with pytest.raises(error, match="defender_id"):
        env.decode_action(defender_id, 0)


def test_configured_server_order_and_ids_not_sorting_or_spelling():
    config = read_world_config(TEST_WORLD / "world_config.toml")
    config["zones"]["A"]["servers"] = ["A3", "A1", "A2"]
    validate_world_config(config)
    before = deepcopy(config)
    choices = build_defender_action_choices(config, "A")
    assert decode_action_choice(choices, 1) == ("inspect", "A3")
    assert decode_action_choice(choices, 6) == ("isolate", "A1")
    assert decode_action_choice(choices, 11) == ("restore", "A2")
    assert config == before


def test_choices_are_immutable_and_independent_of_world_truth_and_busy_status():
    env = WorldEnvironment(world_settings())
    choices = env.action_choices("A")
    with pytest.raises(TypeError):
        choices[0] = ("restore", "A1")
    env.start_action("A", "restore", "A1")
    env.state.hosts["B2"].compromised = True
    env.state.attack_jobs["B2"] = AttackJob("A2", 1)
    before = deepcopy(env.state)
    assert env.action_choices("A") == choices
    assert env.decode_action("A", 3) == ("restore", "A1")
    assert env.state == before
    env.reset()
    assert env.action_choices("A") == choices


@pytest.mark.parametrize("submit_busy", [False, True])
def test_decoded_busy_commands_follow_existing_reject_or_continue_rules(submit_busy):
    env = WorldEnvironment(world_settings())
    env.step({"A": env.decode_action("A", 3), "B": env.decode_action("B", 0)})
    commands = {"B": env.decode_action("B", 0)}
    if submit_busy:
        commands["A"] = env.decode_action("A", 6)
    report = env.step(commands)
    assert report["defender_command_results"].get("A") == ("rejected" if submit_busy else None)
    assert env.state.defenders["A"].job.action == "restore"
    assert env.state.defenders["A"].job.remaining_steps == 2
    assert not env.state.hosts["A2"].isolated


def test_number_translation_and_literal_commands_produce_identical_episode():
    numeric, literal = WorldEnvironment(world_settings()), WorldEnvironment(world_settings())
    # Restore, continue, reconnect, inspect, isolate, already-isolated, then Wait.
    plan = [
        ({"A": 3, "B": 0}, {"A": ("restore", "A1"), "B": ("wait", None)}),
        ({"B": 0}, {"B": ("wait", None)}),
        ({"B": 0}, {"B": ("wait", None)}),
        ({"B": 0}, {"B": ("wait", None)}),
        ({"A": 4, "B": 0}, {"A": ("reconnect", "A1"), "B": ("wait", None)}),
        ({"A": 5, "B": 0}, {"A": ("inspect", "A2"), "B": ("wait", None)}),
        ({"B": 0}, {"B": ("wait", None)}),
        ({"A": 6, "B": 0}, {"A": ("isolate", "A2"), "B": ("wait", None)}),
        ({"A": 6, "B": 0}, {"A": ("isolate", "A2"), "B": ("wait", None)}),
    ]
    for interval in range(50):
        ids, commands = plan[interval] if interval < len(plan) else (
            {"A": 0, "B": 0}, {"A": ("wait", None), "B": ("wait", None)}
        )
        decoded = {zone: numeric.decode_action(zone, number) for zone, number in ids.items()}
        assert decoded == commands
        numeric_report = numeric.step(decoded)
        assert numeric_report == literal.step(commands)
        assert numeric.state == literal.state
        for zone in ("A", "B"):
            assert numeric.observe(zone) == literal.observe(zone)
        if interval == 8:
            assert numeric_report["defender_command_results"]["A"] == "already_satisfied"
    assert numeric_report["episode_finished"]
    assert numeric.action_choices("A") == build_defender_action_choices(read_world_config(TEST_WORLD / "world_config.toml"), "A")


def test_decoding_alone_does_not_execute_selected_isolation():
    env = WorldEnvironment(world_settings())
    before = deepcopy(env.state)
    commands = {"A": env.decode_action("A", 2), "B": env.decode_action("B", 0)}
    assert env.state == before
    report = env.step(commands)
    assert report["elapsed_steps"] == 1
    assert report["defender_command_results"] == {"A": "accepted", "B": "accepted"}
    assert report["defender_completions"] == {"A": "isolate"}
    assert env.state.hosts["A1"].isolated
    assert env.observe("A")["job_action"] == 0
    assert env.observe("A")["last_command_feedback"] == 1
