from random import Random

import numpy as np
import pytest

from checks.scenario_helpers import RANDOM_INTRUSION, TEST_SETTINGS, world_settings
from learning.imitation import TEACHERS, teacher_policies
from learning.imitation_config import read_imitation_config, validate_imitation_config
from observations.schema import observation_feature_names
from policies.inspect_then_restore import InspectThenRestore
from policies.restore_reconnect_only_when_helpful import RestoreReconnectOnlyWhenHelpful
from world.environment import WorldEnvironment
from world.state import EpisodeScript, FalseWarning, Intrusion

# random intrusions, and a finished Restore patches its server
PATCHING = {**RANDOM_INTRUSION, "actions.restore.patches_server": True}


def play(tmp_path, rule, scripts, teachers=None):

    environment = WorldEnvironment(world_settings(PATCHING))
    if teachers is None:
        teachers = teacher_policies(environment, rule)

    episodes = []
    for script in scripts:
        environment.reset()
        environment.state.script = script

        commands = {}
        for defender_id in teachers:
            commands[defender_id] = []
        total = 0.0

        while not environment.is_episode_finished():
            interval = environment.state.elapsed_steps
            chosen = {}
            for defender_id, teacher in teachers.items():
                if environment.state.defenders[defender_id].job is None:
                    observation = np.asarray(environment.encode_observation(defender_id))
                    action, target = environment.decode_action(defender_id, teacher(observation))
                    chosen[defender_id] = (action, target)
                    if action != "wait":
                        commands[defender_id].append((interval, action, target))
            total += environment.step(chosen)["reward"]["shared_reward"]

        episodes.append((commands, total))
    return episodes


def test_on_a_false_warning_the_restore_teacher_restores_a_clean_server_and_the_inspect_teacher_only_inspects(tmp_path):
    script = EpisodeScript(false_warnings=(FalseWarning(server="A2", interval=5),))

    (commands, total), = play(tmp_path, "restore-on-warning", [script])
    assert commands == {"A": [(6, "restore", "A2"), (10, "reconnect", "A2")], "B": []}
    assert total == -12.0

    (commands, total), = play(tmp_path, "inspect-then-restore", [script])
    assert commands == {"A": [(6, "inspect", "A2")], "B": []}
    assert total == 0.0


def test_on_a_real_intrusion_the_inspect_teacher_restores_each_server_two_intervals_later(tmp_path):
    script = EpisodeScript(intrusion=Intrusion(server="A2", interval=5))

    (restore_first, _), = play(tmp_path, "restore-on-warning", [script])
    assert restore_first == {"A": [(7, "restore", "A2"), (11, "reconnect", "A2")],
                             "B": [(13, "restore", "B2"), (17, "reconnect", "B2")]}

    (inspect_first, _), = play(tmp_path, "inspect-then-restore", [script])
    assert inspect_first == {"A": [(7, "inspect", "A2"), (9, "restore", "A2"), (13, "reconnect", "A2")],
                             "B": [(13, "inspect", "B2"), (15, "restore", "B2"), (19, "reconnect", "B2")]}


@pytest.mark.parametrize("rule", list(TEACHERS))
def test_a_missed_warning_leaves_its_defender_doing_nothing(tmp_path, rule):
    script = EpisodeScript(intrusion=Intrusion(server="A2", interval=5), missed_servers=("A2",))
    (commands, _), = play(tmp_path, rule, [script])
    assert commands["A"] == []
    assert commands["B"][0][1:] in (("restore", "B2"), ("inspect", "B2"))


def test_two_warnings_that_arrive_together_are_both_handled(tmp_path):
    script = EpisodeScript(false_warnings=(FalseWarning(server="A2", interval=5), FalseWarning(server="A3", interval=5)))

    (commands, _), = play(tmp_path, "restore-on-warning", [script])
    assert commands["A"] == [(6, "restore", "A2"), (10, "reconnect", "A2"), (11, "restore", "A3"), (15, "reconnect", "A3")]

    (commands, _), = play(tmp_path, "inspect-then-restore", [script])
    assert commands["A"] == [(6, "inspect", "A2"), (8, "inspect", "A3")]


def test_a_reconnect_comes_first_then_a_known_infection_then_a_warning_to_check(tmp_path):
    script = EpisodeScript(intrusion=Intrusion(server="A2", interval=5),
                           false_warnings=(FalseWarning(server="A3", interval=7),))

    (commands, _), = play(tmp_path, "restore-on-warning", [script])
    assert commands["A"] == [(7, "restore", "A2"), (11, "reconnect", "A2"), (12, "restore", "A3"), (16, "reconnect", "A3")]

    (commands, _), = play(tmp_path, "inspect-then-restore", [script])
    assert commands["A"] == [(7, "inspect", "A2"), (9, "restore", "A2"), (13, "reconnect", "A2"), (14, "inspect", "A3")]


FIRST_ACTION = {"restore-on-warning": "restore", "inspect-then-restore": "inspect",
                "inspect-then-restore-prob-restore-weakened": "inspect"}


@pytest.mark.parametrize("rule", list(TEACHERS))
def test_world_reset_clears_pending_evidence_for_a_reused_stateless_teacher(tmp_path, rule):
    unfinished = EpisodeScript(false_warnings=(FalseWarning(server="A2", interval=47), FalseWarning(server="A3", interval=47)))
    environment = WorldEnvironment(world_settings(PATCHING))
    teachers = teacher_policies(environment, rule)

    (first, _), (second, _) = play(tmp_path, rule, [unfinished, EpisodeScript()], teachers=teachers)
    assert first["A"][0] == (48, FIRST_ACTION[rule], "A2")
    assert second == {"A": [], "B": []}


@pytest.mark.parametrize("teacher_class", [RestoreReconnectOnlyWhenHelpful, InspectThenRestore])
def test_a_teacher_never_reads_the_request_results_so_it_cannot_follow_the_cue(tmp_path, teacher_class):
    noisy = world_settings({**PATCHING,
                            "observations.warnings": {"false_warnings_per_episode": 2, "miss_share": 0.25,
                                                      "interval_range": [0, 40]},
                            "world.outages": {"per_episode": 1, "duration_steps": 3, "interval_range": [0, 40],
                                              "servers": ["A1", "A2", "A3", "B1", "B2", "B3"]}})

    names = observation_feature_names(3)
    groups = []
    for server in range(1, 4):
        for kind in ("employee_request_result", "peer_request_result"):
            group = []
            for outcome in ("unknown", "failed", "succeeded"):
                group.append(names.index(f"server_{server}.{kind}.{outcome}"))
            groups.append(group)

    environment = WorldEnvironment(noisy)
    environment.set_world_rng(3)
    playing = {}
    twins = {}
    for defender_id in environment.get_defender_ids():
        playing[defender_id] = teacher_class(3)
        twins[defender_id] = teacher_class(3)
    scramble = Random(0)

    decisions = 0
    for _ in range(40):
        environment.reset()
        while not environment.is_episode_finished():
            chosen = {}
            for defender_id in environment.get_defender_ids():
                if environment.state.defenders[defender_id].job is not None:
                    continue
                observation = np.asarray(environment.encode_observation(defender_id))
                scrambled = observation.copy()
                for group in groups:
                    for position in group:
                        scrambled[position] = 0.0
                    scrambled[scramble.choice(group)] = 1.0
                action_id = playing[defender_id](observation)
                assert twins[defender_id](scrambled) == action_id
                chosen[defender_id] = environment.decode_action(defender_id, action_id)
                decisions += 1
            environment.step(chosen)
    assert decisions > 1000


def test_the_warm_start_settings_name_the_teacher_it_copies(tmp_path):
    settings = read_imitation_config(TEST_SETTINGS / "imitation_config.toml")
    assert settings["teacher"]["rule"] == "inspect-then-restore"

    environment = WorldEnvironment(world_settings(PATCHING))
    for rule, teacher_class in TEACHERS.items():
        teachers = teacher_policies(environment, rule)
        for defender_id in ("A", "B"):
            assert type(teachers[defender_id]) is teacher_class

    with pytest.raises(ValueError, match="rule"):
        teacher_policies(environment, "clever")

    for broken in ({"episodes": 600}, {"rule": "clever", "episodes": 600}, {"rule": "restore-on-warning", "episodes": 600, "extra": 1}):
        changed = read_imitation_config(TEST_SETTINGS / "imitation_config.toml")
        changed["teacher"] = broken
        with pytest.raises(ValueError, match="teacher"):
            validate_imitation_config(changed)
