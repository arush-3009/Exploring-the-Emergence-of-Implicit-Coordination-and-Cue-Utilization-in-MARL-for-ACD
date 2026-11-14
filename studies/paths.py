from pathlib import Path

from studies.definitions import A_WAITS_BASELINE, STUDIES, Study

STUDY_TITLES = {1: "Study 1, the receiver, does B use A's interruptions?",
                2: "Study 2, both defenders from the teacher, both learning",
                3: "Study 3, A from random weights next to a fixed B",
                4: "Study 4, A from the teacher next to a fixed B",
                5: "Study 5, A inherited from study 1 next to a fixed B"}


def study_title(folder: str) -> str:
    for number, study in STUDIES.items():
        if study.folder == folder:
            return STUDY_TITLES[number]
    raise ValueError(f"{folder} is not a study folder")


def roots(smoke: bool, full: bool = False) -> tuple[Path, Path]:

    if smoke and full:
        return Path("runs/full-smoke/experiment-runs"), Path("runs/full-smoke/runs")
    
    if smoke:
        return Path("runs/smoke/experiment-runs"), Path("runs/smoke/runs")
    
    return Path("experiment-runs"), Path("runs")


def study_folder(study: Study) -> Path:
    return Path(study.folder)


def world_folder(study: Study, world: str) -> Path:
    return study_folder(study) / "worlds" / world


def arm_folder(study: Study, world: str, arm: str) -> Path:
    return world_folder(study, world) / "training-arms" / arm


def team_folder(study: Study, world: str, arm: str, seed: int) -> Path:
    return arm_folder(study, world, arm) / "teams" / f"seed{seed}-team"


def before_folder(study: Study, world: str, arm: str, seed: int) -> Path:
    return team_folder(study, world, arm, seed) / "before"


def baseline_folder(study: Study, world: str, rule: str) -> Path:
    return world_folder(study, world) / "baselines" / rule


def a_waits_folder(study: Study, world: str, arm: str, seed: int) -> Path:
    return world_folder(study, world) / "baselines" / A_WAITS_BASELINE / arm / f"seed{seed}"


def control_folder(study: Study, world: str, control: str, seed: int) -> Path:
    return world_folder(study, world) / "controls" / control / f"seed{seed}-team"


def probe_list_file(study: Study, world: str, seed: int) -> Path:
    return world_folder(study, world) / "probes" / f"seed{seed}-probe-list.csv"



def probe_sources_file(study: Study, world: str, seed: int) -> Path:
    return world_folder(study, world) / "probes" / f"seed{seed}-probe-sources.csv"


def probe_answers_file(folder: Path) -> Path:
    return folder / "probe_answers.csv"


def evaluation_files(study: Study) -> tuple[str, ...]:

    if study.kind == "sender":
        return ("episodes.csv", "interruptions.csv", "opportunities.csv", "team_measurements.csv")
    
    return ("episodes.csv", "team_measurements.csv")



def figure_names(study: Study, level: str) -> tuple[str, ...]:

    if level == "world" and study.kind == "receiver":
        return ("W1-performance", "W2-behaviour", "W3-controls", "W4-learning")
    if level == "world":
        return ("W1-performance", "W2-signalling", "W3-controls", "W4-learning", "W5-probe")
    if study.kind == "receiver":
        return ("S1-performance", "S2-behaviour", "S3-controls")
    
    return ("S1-performance", "S2-signalling", "S3-controls", "S4-probe")



def public_files(study: Study) -> list[Path]:

    sender = study.kind == "sender"
    evaluation = evaluation_files(study)
    files = []

    for name in ("README.md", "measurements.csv", "master_table.csv"):
        files.append(study_folder(study) / name)
        
    for figure in figure_names(study, "study"):
        for extension in (".png", ".svg", ".csv"):
            files.append(study_folder(study) / "figures" / f"{figure}{extension}")

    for world in study.worlds:
        for name in ("README.md", "world_table.csv"):
            files.append(world_folder(study, world) / name)
        for figure in figure_names(study, "world"):
            for extension in (".png", ".svg", ".csv"):
                files.append(world_folder(study, world) / "figures" / f"{figure}{extension}")

        for arm in study.arms:
            arm_names = ["arm_summary.csv", "learning_curve.csv"]
            if sender:
                arm_names.append("training_behaviour.csv")
            for name in arm_names:
                files.append(arm_folder(study, world, arm) / name)

            for seed in study.seeds:
                team = team_folder(study, world, arm, seed)
                team_names = ["run.json", *evaluation, "learning_curve.csv", "weights/initial.pt", "weights/final.pt"]
                if sender:
                    team_names.append("training_behaviour.csv")
                for name in team_names:
                    files.append(team / name)
                if sender:
                    for name in evaluation:
                        files.append(before_folder(study, world, arm, seed) / name)

        for rule in study.baselines:
            if rule == A_WAITS_BASELINE:
                for arm in study.arms:
                    for seed in study.seeds:
                        for name in evaluation:
                            files.append(a_waits_folder(study, world, arm, seed) / name)
            else:
                for name in evaluation:
                    files.append(baseline_folder(study, world, rule) / name)

        for control in study.controls:
            for seed in study.seeds:
                for name in (*evaluation, "paired.csv"):
                    files.append(control_folder(study, world, control, seed) / name)

    return files


def cross_study_files() -> list[Path]:

    files = []
    for extension in (".csv", ".png", ".svg"):
        files.append(Path(f"sender-studies-summary{extension}"))
    return files


def folder_label(relative: str) -> str:

    parts = relative.split("/")
    if parts[0] == "training-arms" and len(parts) == 4:
        return f"{parts[1]}-{parts[3].removesuffix('-team')}"
    if parts[0] == "training-arms" and len(parts) == 5 and parts[4] == "before":
        return f"{parts[1]}-{parts[3].removesuffix('-team')}-before"
    if parts[0] == "controls" and len(parts) == 3:
        return f"{parts[1]}-{parts[2].removesuffix('-team')}"
    if parts[0] == "baselines" and len(parts) == 2:
        return parts[1]
    if parts[0] == "baselines" and len(parts) == 4 and parts[1] == A_WAITS_BASELINE:
        return f"a-waits-{parts[2]}-{parts[3]}"
    raise ValueError(f"{relative} is not an evaluation folder of a world")
