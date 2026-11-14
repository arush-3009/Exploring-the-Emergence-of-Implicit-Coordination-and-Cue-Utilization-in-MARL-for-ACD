import pytest

from checks.scenario_helpers import TEST_WORLD
from learning.imitation_config import read_imitation_config
from learning.training_config import read_training_config
from studies.definitions import CONTROLS, MASKS, SENDER_WORLD, STUDIES, WORLDS
from world.environment import WorldEnvironment
from world.settings import apply_overrides, load_world_settings

ROOT = TEST_WORLD.parents[1]


def test_an_override_sets_its_key_creates_an_optional_table_and_leaves_the_input_alone():
    settings = load_world_settings(TEST_WORLD)
    changed = apply_overrides(settings, {"rewards.compromise_penalties_by_zone.A": 0.0,
                                         "world.episode.max_steps": 7})
    assert changed["rewards"]["compromise_penalties_by_zone"] == {"A": 0.0}
    assert changed["world"]["episode"]["max_steps"] == 7
    assert "compromise_penalties_by_zone" not in settings["rewards"]
    assert settings["world"]["episode"]["max_steps"] == 50
    report = WorldEnvironment(changed).step({"A": ("wait", None), "B": ("wait", None)})
    assert report["reward"]["compromise_cost_by_zone"] == {"A": 0.0, "B": 0.0}


@pytest.mark.parametrize("overrides,message", [
    ({"observations.masks.suppress_peer_failure_when_local_available": ["B"]}, "masks"),
    ({"observation.masks.hide_peer_request_result": ["B"]}, "settings must hold exactly"),
    ({"observations.masks.hide_peer_request_result": ["C"]}, "unknown zone"),
    ({"rewards.penalties.per_failed_request": -1}, "non-negative"),
    ({"rewards.compromise_penalties_by_zone.C": 0.0}, "Unknown reward zones"),
    ({"observations.masks.hide_peer_request_result": ["B"],
      "observations.masks.suppress_peer_failures_when_local_available": ["B"]}, "hide and suppress"),
])
def test_a_misspelt_or_invalid_override_raises(overrides, message):
    with pytest.raises(ValueError, match=message):
        apply_overrides(load_world_settings(TEST_WORLD), overrides)


def test_every_arm_and_control_of_every_study_applies_to_every_world():
    control_names = []
    for name in MASKS:
        control_names.append(name + "-at-evaluation")
    assert list(CONTROLS) == control_names
    for world in WORLDS:
        base = load_world_settings(ROOT / "worlds" / world)
        for study in STUDIES.values():
            for arm, overrides in study.arms.items():
                settings = apply_overrides(base, {**study.world_overrides, **overrides})
                masks = settings["observations"]["masks"]
                assert masks.get("hide_peer_request_result", []) == (["B"] if arm == "cue-hidden-unknown" else [])
                assert masks.get("suppress_peer_failures_when_local_available", []) == (
                    ["B"] if arm == "cue-hidden-failures-suppressed" else [])
                assert settings["rewards"].get("compromise_penalties_by_zone") == (
                    None if study.kind == "receiver" else {"A": 0.0})
                if arm == "cue-visible":
                    for control in study.controls:
                        apply_overrides(settings, CONTROLS[control])
    assert SENDER_WORLD == {"rewards.compromise_penalties_by_zone.A": 0.0}


def test_the_experiment_settings_files_hold_the_studies_values():
    training = read_training_config(ROOT / "studies/settings/training_config.toml")
    assert training == {"networks": {"hidden_sizes": [64, 64]},
                        "advantages": {"gamma": 0.99, "gae_lambda": 0.95},
                        "ppo": {"actor_learning_rate": 0.0003, "critic_learning_rate": 0.01, "clip_epsilon": 0.2,
                                "epochs": 4, "minibatch_size": 64, "entropy_coefficient": 0.001},
                        "training": {"episodes_per_iteration": 16, "iterations": 3000}}
    imitation = read_imitation_config(ROOT / "studies/settings/imitation_config.toml")
    assert imitation == {"teacher": {"rule": "inspect-then-restore", "episodes": 600},
                         "actor_fit": {"epochs": 300, "learning_rate": 0.001, "minibatch_size": 256,
                                       "action_target_weight": 0.95, "wait_target_weight": 0.6},
                         "critic_fit": {"epochs": 30, "learning_rate": 0.001, "minibatch_size": 256}}
    assert STUDIES[4].training_overrides == {"imitation.teacher.rule": "inspect-then-restore-prob-restore-weakened",
                                             "imitation.actor_fit.restore_target_weight": 0.6}
    assert STUDIES[2].training_overrides == {}
    assert STUDIES[2].defender_imitation_overrides == {"A": {"actor_fit.restore_target_weight": 0.6}}
    for number in (1, 3, 4, 5):
        assert STUDIES[number].defender_imitation_overrides == {}
