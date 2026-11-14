import json

import pytest
import torch

from learning.imitation import soft_targets
from learning.ippo_trainer import IPPOTrainer
from studies import jobs, launch
from studies.definitions import SMOKE, STUDIES
from studies.paths import roots, team_folder
from studies.plan import learning_settings, smoke_study, world_settings
from world.environment import WorldEnvironment

WORLD = SMOKE["world"]
PUBLIC, PRIVATE = roots(True)


def equal(first, second):
    for network in ("actor", "critic"):
        if first[network].keys() != second[network].keys():
            return False
        for key in first[network]:
            if not torch.equal(first[network][key], second[network][key]):
                return False
    return True


def files_of(root):
    files = {}
    for path in root.rglob("*"):
        if path.is_file() and "logs" not in path.parts:
            files[path.relative_to(root)] = path
    return files


def without_times(data):
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if key not in ("started", "finished"):
                result[key] = without_times(value)
        return result
    if isinstance(data, list):
        result = []
        for value in data:
            result.append(without_times(value))
        return result
    return data


def test_serial_and_parallel_runs_give_identical_files(smoke_run, tmp_path, monkeypatch):
    for path in (smoke_run / PRIVATE).rglob("handpicked.toml"):
        copy = tmp_path / PRIVATE / path.relative_to(smoke_run / PRIVATE)
        copy.parent.mkdir(parents=True)
        copy.write_bytes(path.read_bytes())
    monkeypatch.chdir(tmp_path)
    launch.main(["--all", "--smoke", "--jobs", "1"])

    serial = files_of(tmp_path / "runs/smoke")
    parallel = files_of(smoke_run / "runs/smoke")
    assert serial.keys() == parallel.keys()
    assert len(serial) > 1000
    for relative, path in serial.items():
        first, second = path.read_bytes(), parallel[relative].read_bytes()
        if relative.suffix == ".json":
            assert without_times(json.loads(first)) == without_times(json.loads(second)), relative
        else:
            assert first == second, relative


def test_a_fixed_b_is_byte_identical_to_its_study_1_source_before_and_after_training(smoke_run):
    for number in (3, 4, 5):
        study = smoke_study(STUDIES[number])
        for arm in study.arms:
            for seed in study.seeds:
                team = smoke_run / PUBLIC / team_folder(study, WORLD, arm, seed)
                source_file = smoke_run / PUBLIC / team_folder(STUDIES[1], WORLD, "cue-visible", seed) / "weights/final.pt"
                source = torch.load(source_file, weights_only=True)["B"]
                initial = torch.load(team / "weights/initial.pt", weights_only=True)
                final = torch.load(team / "weights/final.pt", weights_only=True)
                assert equal(initial["B"], source)
                assert equal(final["B"], source)
                assert not equal(initial["A"], final["A"])

                fixed = json.loads((team / "run.json").read_text())["fixed_defenders"]["B"]
                assert fixed["equal_before_training"] and fixed["equal_after_training"]
                assert fixed["weights_hash"] == jobs.weights_hash(source)


def test_the_training_job_refuses_a_fixed_b_that_is_not_its_source(smoke_run, tmp_path):
    initial = smoke_run / PUBLIC / team_folder(smoke_study(STUDIES[3]), WORLD, "cue-visible", 0) / "weights/initial.pt"
    other = smoke_run / PUBLIC / team_folder(STUDIES[1], WORLD, "cue-visible", 1) / "weights/final.pt"
    training, _ = learning_settings(STUDIES[3], True)
    with pytest.raises(AssertionError, match="the fixed B's weights differ"):
        jobs.train(world_settings(STUDIES[3], WORLD, []), training, 0, None, True, initial, other, None,
                   tmp_path / "public", tmp_path / "private", {}, {})


def test_random_initial_weights_are_the_ones_the_trainer_s_seed_scheme_draws(smoke_run):
    training, _ = learning_settings(STUDIES[2], True)
    for number, defenders in ((3, ("A",)),):
        study = smoke_study(STUDIES[number])
        for arm, mask in study.arms.items():
            for seed in study.seeds:
                trainer = IPPOTrainer(WorldEnvironment(world_settings(study, WORLD, [mask])), training, seed)
                file = smoke_run / PUBLIC / team_folder(study, WORLD, arm, seed) / "weights/initial.pt"
                initial = torch.load(file, weights_only=True)
                for defender in defenders:
                    learner = trainer.learners[defender]
                    assert equal(initial[defender], {"actor": learner.actor.state_dict(),
                                                     "critic": learner.critic.state_dict()})


def test_the_weakened_restore_target_changes_only_the_restore_rows_of_the_soft_targets():
    choices = WorldEnvironment(world_settings(STUDIES[4], WORLD, [])).action_choices("A")
    action_ids = torch.arange(len(choices))
    plain = soft_targets(action_ids, len(choices), 0.95, 0.6)
    weakened = soft_targets(action_ids, len(choices), 0.95, 0.6, restore_target_weight=0.6, action_choices=choices)

    restores = 0
    for action_id, (action, _) in enumerate(choices):
        if action == "restore":
            restores += 1
            for other in range(len(choices)):
                expected = 0.6 if other == action_id else 0.4 / (len(choices) - 1)
                assert weakened[action_id, other].item() == pytest.approx(expected)
            assert not torch.equal(weakened[action_id], plain[action_id])
        else:
            assert torch.equal(weakened[action_id], plain[action_id])
    assert restores == 3

    assert learning_settings(STUDIES[4], False)[1]["actor_fit"]["restore_target_weight"] == 0.6
    for number in (1, 2, 3, 5):
        assert "restore_target_weight" not in learning_settings(STUDIES[number], False)[1]["actor_fit"]


def test_study_4_s_warm_start_fits_a_on_study_1_s_teacher_episodes(smoke_run):
    for seed in SMOKE["seeds"]:
        teams = {}
        for number in (1, 4):
            teams[number] = team_folder(smoke_study(STUDIES[number]), WORLD, "cue-visible", seed)
        first = json.loads((smoke_run / PRIVATE / teams[1] / "warm_start.json").read_text())
        fourth = json.loads((smoke_run / PRIVATE / teams[4] / "warm_start.json").read_text())
        assert first["fitted"] == ["A", "B"]
        assert fourth["fitted"] == ["A"]
        assert fourth["world_seed"] == first["world_seed"]
        assert fourth["defender_seeds"] == first["defender_seeds"]
        for count in ("decisions", "action_decisions"):
            assert fourth["fit"]["A"]["actor"][count] == first["fit"]["A"]["actor"][count]

        initial = {}
        for number in (1, 4):
            initial[number] = torch.load(smoke_run / PUBLIC / teams[number] / "weights/initial.pt", weights_only=True)
        assert not equal(initial[1]["A"], initial[4]["A"])


def test_study_2_s_warm_start_gives_a_study_4_s_a_and_study_1_s_b_actor(smoke_run):
    for seed in SMOKE["seeds"]:
        teams = {}
        for number in (1, 2, 4):
            teams[number] = team_folder(smoke_study(STUDIES[number]), WORLD, "cue-visible", seed)
        first = json.loads((smoke_run / PRIVATE / teams[1] / "warm_start.json").read_text())
        second = json.loads((smoke_run / PRIVATE / teams[2] / "warm_start.json").read_text())
        assert second["fitted"] == ["A", "B"]
        assert second["world_seed"] == first["world_seed"]
        assert second["defender_seeds"] == first["defender_seeds"]
        assert second["imitation"]["teacher"]["rule"] == "inspect-then-restore"
        assert second["imitation_by_defender"]["A"]["actor_fit"]["restore_target_weight"] == 0.6
        assert "restore_target_weight" not in second["imitation_by_defender"]["B"]["actor_fit"]
        assert second["imitation_by_defender"]["B"] == second["imitation"]

        initial = {}
        for number in (1, 2, 4):
            initial[number] = torch.load(smoke_run / PUBLIC / teams[number] / "weights/initial.pt", weights_only=True)
        assert equal(initial[2]["A"], initial[4]["A"])
        for key in initial[1]["B"]["actor"]:
            assert torch.equal(initial[2]["B"]["actor"][key], initial[1]["B"]["actor"][key])
        assert not equal(initial[2]["B"], initial[1]["B"])

