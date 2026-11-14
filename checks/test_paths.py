from pathlib import Path

from studies.definitions import STUDIES
from studies.paths import cross_study_files, public_files, roots

FOLDERS = {1: "study-1-receiver-cue-utilization", 2: "study-2-sender-joint-teacher-start",
           3: "study-3-sender-random-a-fixed-b", 4: "study-4-sender-teacher-a-fixed-b",
           5: "study-5-sender-inherited-a-fixed-b"}


def test_study_folders_and_roots():
    for number, study in STUDIES.items():
        assert study.folder == FOLDERS[number]
    assert roots(False) == (Path("experiment-runs"), Path("runs"))
    assert roots(True) == (Path("runs/smoke/experiment-runs"), Path("runs/smoke/runs"))
    assert roots(True, True) == (Path("runs/full-smoke/experiment-runs"), Path("runs/full-smoke/runs"))
    names = []
    for path in cross_study_files():
        names.append(str(path))
    assert names == ["sender-studies-summary.csv", "sender-studies-summary.png", "sender-studies-summary.svg"]


def files_under(study_number, folder):
    inside = []
    for path in public_files(STUDIES[study_number]):
        if folder in path.parents:
            inside.append(str(path.relative_to(folder)))
    return sorted(inside)


def test_study_1_has_exactly_its_public_files():
    study = Path(FOLDERS[1])
    world = study / "worlds" / "reliable-warnings"
    assert files_under(1, study / "figures") == sorted([
        "S1-performance.png", "S1-performance.svg", "S1-performance.csv", "S2-behaviour.png", "S2-behaviour.svg",
        "S2-behaviour.csv", "S3-controls.png", "S3-controls.svg", "S3-controls.csv"])
    assert files_under(1, world / "training-arms" / "cue-hidden-unknown" / "teams" / "seed4-team") == sorted([
        "run.json", "team_measurements.csv", "episodes.csv", "learning_curve.csv", "weights/initial.pt",
        "weights/final.pt"])
    assert files_under(1, world / "training-arms" / "cue-visible") == sorted(
        ["arm_summary.csv", "learning_curve.csv"] + files_in_teams(["run.json", "team_measurements.csv", "episodes.csv",
                                                                    "learning_curve.csv", "weights/initial.pt",
                                                                    "weights/final.pt"]))
    assert files_under(1, world / "baselines") == sorted([
        "always-wait/episodes.csv", "always-wait/team_measurements.csv",
        "inspect-teacher/episodes.csv", "inspect-teacher/team_measurements.csv",
        "restore-teacher/episodes.csv", "restore-teacher/team_measurements.csv",
        "random/episodes.csv", "random/team_measurements.csv"])
    assert files_under(1, world / "controls" / "cue-hidden-failures-suppressed-at-evaluation" / "seed0-team") == sorted([
        "episodes.csv", "team_measurements.csv", "paired.csv"])
    assert files_under(1, world / "figures") == sorted([
        "W1-performance.png", "W1-performance.svg", "W1-performance.csv", "W2-behaviour.png", "W2-behaviour.svg",
        "W2-behaviour.csv", "W3-controls.png", "W3-controls.svg", "W3-controls.csv", "W4-learning.png",
        "W4-learning.svg", "W4-learning.csv"])
    assert files_under(1, study) == sorted(top_files(1))


def files_in_teams(names):
    files = []
    for seed in range(5):
        for name in names:
            files.append(f"teams/seed{seed}-team/{name}")
    return files


def top_files(number):
    sender = number > 1
    evaluation = ["episodes.csv", "interruptions.csv", "opportunities.csv", "team_measurements.csv"] if sender else [
        "episodes.csv", "team_measurements.csv"]
    figures = ["S1-performance", "S2-signalling", "S3-controls", "S4-probe"] if sender else [
        "S1-performance", "S2-behaviour", "S3-controls"]
    world_figures = ["W1-performance", "W2-signalling", "W3-controls", "W4-learning", "W5-probe"] if sender else [
        "W1-performance", "W2-behaviour", "W3-controls", "W4-learning"]
    arms = ["cue-visible", "cue-hidden-failures-suppressed"] if sender else ["cue-visible", "cue-hidden-unknown"]
    files = ["README.md", "measurements.csv", "master_table.csv"]
    for figure in figures:
        for extension in (".png", ".svg", ".csv"):
            files.append(f"figures/{figure}{extension}")
    for world in STUDIES[number].worlds:
        w = f"worlds/{world}"
        files.extend([f"{w}/README.md", f"{w}/world_table.csv"])
        for figure in world_figures:
            for extension in (".png", ".svg", ".csv"):
                files.append(f"{w}/figures/{figure}{extension}")
        for arm in arms:
            files.extend([f"{w}/training-arms/{arm}/arm_summary.csv", f"{w}/training-arms/{arm}/learning_curve.csv"])
            if sender:
                files.append(f"{w}/training-arms/{arm}/training_behaviour.csv")
            for seed in range(5):
                team = f"{w}/training-arms/{arm}/teams/seed{seed}-team"
                for name in ["run.json", *evaluation, "learning_curve.csv", "weights/initial.pt", "weights/final.pt"]:
                    files.append(f"{team}/{name}")
                if sender:
                    files.append(f"{team}/training_behaviour.csv")
                    for name in evaluation:
                        files.append(f"{team}/before/{name}")
        for rule in ("always-wait", "inspect-teacher", "restore-teacher", "random"):
            for name in evaluation:
                files.append(f"{w}/baselines/{rule}/{name}")
        if number in (3, 4, 5):
            for arm in arms:
                for seed in range(5):
                    for name in evaluation:
                        files.append(f"{w}/baselines/a-waits-with-fixed-b/{arm}/seed{seed}/{name}")
        for control in ("cue-hidden-unknown-at-evaluation", "cue-hidden-failures-suppressed-at-evaluation"):
            for seed in range(5):
                for name in [*evaluation, "paired.csv"]:
                    files.append(f"{w}/controls/{control}/seed{seed}-team/{name}")
    return files


def test_every_sender_study_has_exactly_its_public_files():
    for number in (2, 3, 4, 5):
        study = Path(FOLDERS[number])
        assert files_under(number, study) == sorted(top_files(number))
        assert len(public_files(STUDIES[number])) == len(set(public_files(STUDIES[number])))
    team = Path(FOLDERS[5]) / "worlds" / "two-false-warnings" / "training-arms" / "cue-visible" / "teams" / "seed2-team"
    assert files_under(5, team / "before") == sorted([
        "episodes.csv", "interruptions.csv", "opportunities.csv", "team_measurements.csv"])
    for number in (2, 3, 4, 5):
        for path in public_files(STUDIES[number]):
            assert path.name != "probe_answers.csv" and "probes" not in path.parts
    assert len(public_files(STUDIES[1])) == 592
    assert len(public_files(STUDIES[2])) == 1110
    assert len(public_files(STUDIES[5])) == 1310
