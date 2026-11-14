import csv
import json
import random
import shutil
from pathlib import Path

from episodes.record_io import read_records, sha256_of
from figures.readme import RECEIVER_COLUMNS, SENDER_COLUMNS, shown
from figures.style import BASELINES
from measurements.episode import SCRIPT_COLUMNS
from measurements.glossary import base_rows
from measurements.tables import read_csv
from studies import launch, regenerate_probes
from studies.definitions import A_WAITS_BASELINE, CONTROLS, SMOKE, STUDIES
from studies.paths import (
    arm_folder,
    before_folder,
    cross_study_files,
    probe_answers_file,
    probe_list_file,
    probe_sources_file,
    public_files,
    roots,
    study_folder,
    team_folder,
    world_folder,
)
from studies.plan import launch_jobs, marker, smoke_study

WORLD = SMOKE["world"]
PUBLIC, PRIVATE = roots(True)

CHOSEN = {
    "study-1-receiver-cue-utilization": {
        "episode-2001-003": ["training-arms/cue-visible/teams/seed0-team",
                             "training-arms/cue-hidden-unknown/teams/seed0-team"],
        "episode-2002-007": ["controls/cue-hidden-unknown-at-evaluation/seed1-team", "baselines/always-wait"]},
    "study-5-sender-inherited-a-fixed-b": {
        "episode-2001-000": ["training-arms/cue-visible/teams/seed0-team",
                             "controls/cue-hidden-failures-suppressed-at-evaluation/seed0-team",
                             "training-arms/cue-visible/teams/seed0-team/before",
                             "baselines/a-waits-with-fixed-b/cue-visible/seed0"]}}
WORLD_PAGES = {
    "study-1-receiver-cue-utilization": [
        "episode-2001-003-cue-visible-seed0__cue-hidden-unknown-seed0.html",
        "episode-2002-007-cue-hidden-unknown-at-evaluation-seed1__always-wait.html"],
    "study-5-sender-inherited-a-fixed-b": [
        ("episode-2001-000-cue-visible-seed0__cue-hidden-failures-suppressed-at-evaluation-seed0__cue-visible-seed0-"
         "before__a-waits-cue-visible-seed0.html")]}


def ids(path):
    result = []
    with path.open(newline="") as file:
        for row in csv.DictReader(file):
            result.append(row["id"])
    return result


def test_the_public_tree_holds_every_file_and_no_other(smoke_run):
    expected = set(cross_study_files())
    for study in STUDIES.values():
        expected.update(public_files(smoke_study(study)))
    for study, episodes in CHOSEN.items():
        world = Path(study) / "worlds" / WORLD
        for name, folders in episodes.items():
            for folder in folders:
                expected.add(world / folder / "traces" / f"{name}.json")
                expected.add(world / folder / "timelines" / f"{name}.html")
        for page in WORLD_PAGES[study]:
            expected.add(world / "timelines" / page)

    actual = set()
    for path in (smoke_run / PUBLIC).rglob("*"):
        if path.is_file():
            actual.add(path.relative_to(smoke_run / PUBLIC))
    assert actual == expected


def test_every_job_left_its_marker_and_every_evaluation_its_records(smoke_run, monkeypatch):
    monkeypatch.chdir(smoke_run)
    graph = launch_jobs(list(STUDIES), True, {})
    kinds = []
    for job in graph:
        kinds.append(job.kind)
    assert kinds.count("handpicked") == 5
    assert kinds.count("measure_cross_study") == 1
    evaluations = 0
    for job in graph:
        assert (smoke_run / marker(PRIVATE, job.id)).is_file(), job.id
        if job.kind == "evaluate":
            folder = smoke_run / PRIVATE / job.id.rsplit("/", 1)[0]
            assert (folder / "records.jsonl.gz").is_file()
            assert json.loads((folder / "run.json").read_text())["episodes_per_seed"] == SMOKE["episodes_per_seed"]
            evaluations += 1
    assert evaluations == 20 + 20 + 16 + 20 + 12


def test_studies_3_to_5_start_from_the_smoke_study_1_teams(smoke_run):
    for number in (3, 4, 5):
        study = smoke_study(STUDIES[number])
        for arm in study.arms:
            for seed in study.seeds:
                info = json.loads((smoke_run / PRIVATE / team_folder(study, WORLD, arm, seed) /
                                   "initial_weights.json").read_text())
                source = PUBLIC / team_folder(STUDIES[1], WORLD, "cue-visible", seed) / "weights/final.pt"
                for defender, start in study.start.items():
                    assert info["defenders"][defender]["start"] == start
                    if start == "study-1-team":
                        assert info["defenders"][defender]["source"] == source.as_posix()
                        assert info["defenders"][defender]["source_sha256"] == sha256_of(smoke_run / source)


def test_each_training_run_json_holds_the_hash_of_its_probe_list(smoke_run):
    for number, study in STUDIES.items():
        study = smoke_study(study)
        for arm in study.arms:
            for seed in study.seeds:
                run = json.loads((smoke_run / PUBLIC / team_folder(study, WORLD, arm, seed) / "run.json").read_text())
                if number == 1:
                    assert run["probe_list"] is None
                    continue
                probes = PRIVATE / probe_list_file(study, WORLD, seed)
                assert run["probe_list"] == {"file": probes.as_posix(), "sha256": sha256_of(smoke_run / probes)}


def test_the_probe_files_are_private(smoke_run):
    for number in (2, 3, 4, 5):
        study = smoke_study(STUDIES[number])
        for seed in study.seeds:
            assert (smoke_run / PRIVATE / probe_list_file(study, WORLD, seed)).exists()
            assert (smoke_run / PRIVATE / probe_sources_file(study, WORLD, seed)).exists()
            assert not (smoke_run / PUBLIC / probe_list_file(study, WORLD, seed)).exists()
            for arm in study.arms:
                for folder in (team_folder(study, WORLD, arm, seed), before_folder(study, WORLD, arm, seed)):
                    assert (smoke_run / PRIVATE / probe_answers_file(folder)).exists()
                    assert not (smoke_run / PUBLIC / probe_answers_file(folder)).exists()


def test_every_sender_team_carries_its_probe_and_before_rows(smoke_run):
    base = []
    for row in base_rows(True):
        base.append(row["id"])
    before = []
    for id in base:
        before.append("before_" + id)

    for number in (2, 3, 4, 5):
        study = smoke_study(STUDIES[number])
        for arm in study.arms:
            for seed in study.seeds:
                team = smoke_run / PUBLIC / team_folder(study, WORLD, arm, seed)
                assert ids(team / "team_measurements.csv") == base + before
                assert ids(smoke_run / PUBLIC / before_folder(study, WORLD, arm, seed) / "team_measurements.csv") == base
    assert sum(id.startswith("probe_") for id in base) == 8


def test_every_team_baseline_and_control_meets_the_same_episodes(smoke_run):
    scripts = set()
    files = 0
    for path in (smoke_run / PUBLIC).rglob("episodes.csv"):
        key = []
        with path.open(newline="") as file:
            for row in csv.DictReader(file):
                cells = [row["evaluation_seed"], row["episode"]]
                for column in SCRIPT_COLUMNS:
                    cells.append(row[column])
                key.append(tuple(cells))
        assert len(key) == len(STUDIES[1].evaluation_seeds) * SMOKE["episodes_per_seed"]
        scripts.add(tuple(key))
        files += 1
    assert files == 88
    assert len(scripts) == 1


def masked(settings):
    result = set()
    for name, defenders in settings["observations"]["masks"].items():
        if defenders:
            result.add((name, tuple(defenders)))
    return result


def mask_of(overrides):
    result = set()
    for key, defenders in overrides.items():
        result.add((key.rsplit(".", 1)[1], tuple(defenders)))
    return result


def test_every_evaluation_and_training_ran_under_its_own_mask(smoke_run):
    studies = {}
    for study in STUDIES.values():
        studies[study.folder] = study
    checked = 0
    for job in launch_jobs(list(STUDIES), True, {}):
        if job.kind not in ("evaluate", "train"):
            continue
        folder = job.id.rsplit("/", 1)[0]
        root = PRIVATE if job.kind == "evaluate" else PUBLIC
        run = json.loads((smoke_run / root / folder / "run.json").read_text())
        if "control" in run:
            expected = mask_of(CONTROLS[run["control"]])
        elif "arm" in run:
            expected = mask_of(studies[run["study"]].arms[run["arm"]])
        else:
            expected = set()
        assert masked(run["settings"]) == expected, folder
        sender = studies[run["study"]].kind == "sender"
        assert run["settings"]["rewards"].get("compromise_penalties_by_zone") == ({"A": 0.0} if sender else None)
        checked += 1

        if job.kind == "evaluate":
            policies = run["policies"]
            if run["kind"] == "baseline" and run["rule"] != A_WAITS_BASELINE:
                assert policies == {"A": {"type": "rule", "rule": run["rule"]}, "B": {"type": "rule", "rule": run["rule"]}}
                continue
            team = PUBLIC / team_folder(studies[run["study"]], run["world"], run["arm"], run["seed"])
            weights = team / ("weights/final.pt" if run["kind"] in ("team-evaluation", "control") else "weights/initial.pt")
            for defender in ("A", "B"):
                if run["kind"] == "baseline" and defender == "A":
                    assert policies["A"] == {"type": "rule", "rule": "always-wait"}
                    continue
                assert policies[defender]["weights"] == weights.as_posix(), folder
                assert policies[defender]["sha256"] == sha256_of(smoke_run / weights)
    assert checked == 88 + 20


def test_each_team_s_seeds_follow_the_seed_schemes(smoke_run):
    for number, study in STUDIES.items():
        study = smoke_study(study)
        for arm in study.arms:
            for seed in study.seeds:
                run = json.loads((smoke_run / PUBLIC / team_folder(study, WORLD, arm, seed) / "run.json").read_text())
                draws = random.Random(seed)
                for _ in range(6):
                    draws.randrange(2**31)
                trainer = draws.randrange(2**31)
                sender_seed = random.Random(seed + 10000 * number).randrange(2**31)
                assert run["world_seed"] == (trainer if number == 1 else sender_seed)

                if "warm-start" in study.start.values():
                    info = json.loads((smoke_run / PRIVATE / team_folder(study, WORLD, arm, seed) /
                                       "warm_start.json").read_text())
                    draws = random.Random(seed)
                    expected = {}
                    for defender in ("A", "B"):
                        expected[defender] = {"weights": draws.randrange(2**31), "sampling": draws.randrange(2**31),
                                              "actor_fit": draws.randrange(2**31), "critic_fit": draws.randrange(2**31)}
                    assert info["defender_seeds"] == expected
                    assert info["world_seed"] == draws.randrange(2**31)


def test_a_sender_team_s_before_rows_are_its_before_folder_s_rows(smoke_run):
    for number in (2, 3, 4, 5):
        study = smoke_study(STUDIES[number])
        for arm in study.arms:
            for seed in study.seeds:
                before = {}
                with (smoke_run / PUBLIC / before_folder(study, WORLD, arm, seed) / "team_measurements.csv").open() as file:
                    for row in csv.DictReader(file):
                        before[row["id"]] = row
                carried = 0
                with (smoke_run / PUBLIC / team_folder(study, WORLD, arm, seed) / "team_measurements.csv").open() as file:
                    for row in csv.DictReader(file):
                        if row["id"].startswith("before_"):
                            plain = row["id"][len("before_"):]
                            assert {**row, "id": plain} == before[plain]
                            carried += 1
                assert carried == len(before)


def test_the_probe_answers_as_the_evaluation_chose(smoke_run):
    checked = {"before": 0, "team": 0}
    for number in (2, 3, 4, 5):
        study = smoke_study(STUDIES[number])
        for seed in study.seeds:
            numbers = {}
            with (smoke_run / PRIVATE / probe_list_file(study, WORLD, seed)).open(newline="") as file:
                for row in csv.DictReader(file):
                    numbers[row["observation"]] = row["probe"]
            for arm in study.arms:
                for kind, folder in (("before", before_folder(study, WORLD, arm, seed)),
                                     ("team", team_folder(study, WORLD, arm, seed))):
                    answers = {}
                    with (smoke_run / PRIVATE / probe_answers_file(folder)).open(newline="") as file:
                        for row in csv.DictReader(file):
                            answers[row["probe"]] = row["greedy"]
                    assert len(answers) == len(numbers)
                    for record in read_records(smoke_run / PRIVATE / folder / "records.jsonl.gz"):
                        for boundary, interval in enumerate(record.intervals):
                            entry = interval["defenders"]["A"]
                            key = json.dumps(record.boundaries[boundary]["observations"]["A"], sort_keys=True)
                            if not entry["free"] or key not in numbers:
                                continue
                            label = entry["action"] if entry["target"] is None else f"{entry['action']}_{entry['target']}"
                            assert answers[numbers[key]] == label
                            checked[kind] += 1
    assert checked["before"] > 1000
    assert checked["team"] > 1000


def by_id(path):
    rows = {}
    for row in read_csv(path):
        rows[(row["id"], row["control"])] = row
    return rows


def test_the_tables_carry_each_team_s_values_and_the_arm_summary_s_means(smoke_run):
    summaries = {}
    for study in STUDIES.values():
        study = smoke_study(study)
        world = read_csv(smoke_run / PUBLIC / world_folder(study, WORLD) / "world_table.csv")
        master = read_csv(smoke_run / PUBLIC / study_folder(study) / "master_table.csv")
        assert len(master) == 1 and master[0]["world"] == WORLD

        for arm in study.arms:
            summary = by_id(smoke_run / PUBLIC / arm_folder(study, WORLD, arm) / "arm_summary.csv")
            for seed in study.seeds:
                team = read_csv(smoke_run / PUBLIC / team_folder(study, WORLD, arm, seed) / "team_measurements.csv")
                row = []
                for candidate in world:
                    if candidate["row"] == "team" and candidate["arm"] == arm and candidate["seed"] == str(seed):
                        row.append(candidate)
                assert len(row) == 1
                for measured in team:
                    assert summary[(measured["id"], "")][f"seed{seed}"] == measured["value"]
                    for column in ("value", "numerator", "denominator"):
                        suffix = "" if column == "value" else f"_{column}"
                        assert row[0][measured["id"] + suffix] == measured[column]

            means = []
            for candidate in world:
                if candidate["row"] == "arm mean" and candidate["arm"] == arm:
                    means.append(candidate)
            assert len(means) == 1
            for (id, control), summarised in summary.items():
                column = id if control == "" else f"{id}__{control}"
                assert means[0][column] == summarised["mean"]
                if f"{column}__{arm}__mean" in master[0]:
                    assert master[0][f"{column}__{arm}__mean"] == summarised["mean"]
                    assert master[0][f"{column}__{arm}__teams"] == summarised["teams"]
                elif control != "":
                    assert master[0][f"{column}__mean"] == summarised["mean"]
            if study.kind == "sender":
                summaries[(study.folder, arm)] = summary[("a_interrupt_relevant", "")]

    rows = read_csv(smoke_run / PUBLIC / "sender-studies-summary.csv")
    assert len(rows) == 4 * 2
    for row in rows:
        summarised = summaries[(row["study"], row["arm"])]
        assert row["a_interrupt_relevant_mean"] == summarised["mean"]
        assert row["teams_at_or_above_1_percent"] == summarised["teams_at_or_above_1_percent"]


def test_each_readme_names_only_files_of_the_public_tree(smoke_run):
    readmes = 0
    for path in (smoke_run / PUBLIC).rglob("README.md"):
        text = path.read_text()
        for link in text.split("](")[1:]:
            target = link.split(")", 1)[0]
            assert (path.parent / target).is_file(), (path, target)
        assert "runs/" not in text.replace("experiment-runs/", "")
        assert "] (" not in text, path
        if path.parent.parent == smoke_run / PUBLIC:
            assert "[measurements.csv](measurements.csv)" in text
        readmes += 1
    assert readmes == 5 * 2


def test_each_readme_shows_the_values_of_its_tables(smoke_run):
    labelled = 0
    rows = 0
    for study in STUDIES.values():
        study = smoke_study(study)
        ids = SENDER_COLUMNS if study.kind == "sender" else RECEIVER_COLUMNS
        world = smoke_run / PUBLIC / world_folder(study, WORLD)
        lines = (world / "README.md").read_text().splitlines()

        shown_rows = []
        below = 0
        a_waits_rows = {}
        for row in read_csv(world / "world_table.csv"):
            cells = []
            for id in ids:
                cells.append(shown(id, row[id]))
            if row["row"] == "team":
                label = f"{row['arm']}, seed {row['seed']}"
                if study.kind == "sender" and row["below_1_percent"] == "1":
                    label += ", under 1 percent interruptions of the attacked pair's server"
                    below += 1
            elif row["row"] == "baseline" and row["arm"] == "":
                label = BASELINES[row["baseline"]][0]
            elif row["row"] == "baseline":
                if row["seed"] not in a_waits_rows:
                    a_waits_rows[row["seed"]] = []
                a_waits_rows[row["seed"]].append((row["arm"], cells))
                continue
            else:
                continue
            shown_rows.append("| " + " | ".join([label, *cells]) + " |")
        for seed, versions in a_waits_rows.items():
            label = BASELINES[A_WAITS_BASELINE][0]
            same = True
            for _, cells in versions:
                if cells != versions[0][1]:
                    same = False
            if same:
                shown_rows.append("| " + " | ".join([f"{label}, seed {seed}", *versions[0][1]]) + " |")
            else:
                for arm, cells in versions:
                    shown_rows.append("| " + " | ".join([f"{label}, {arm}, seed {seed}", *cells]) + " |")
        listed = []
        for line in lines:
            if line in shown_rows:
                listed.append(line)
        assert listed == shown_rows
        labelled += below
        rows += len(shown_rows)

        master = read_csv(smoke_run / PUBLIC / study_folder(study) / "master_table.csv")[0]
        text = (smoke_run / PUBLIC / study_folder(study) / "README.md").read_text()
        for arm in study.arms:
            cells = [f"[{WORLD.replace('-', ' ')}](worlds/{WORLD}/README.md)", arm]
            for id in ids:
                cells.append(f"{shown(id, master[f'{id}__{arm}__mean'])} ({master[f'{id}__{arm}__teams']} teams)")
            assert "| " + " | ".join(cells) + " |" in text
    assert 5 * 8 + 3 * 2 <= rows <= 5 * 8 + 3 * 4
    assert labelled > 0


def test_measuring_and_drawing_again_rebuild_the_same_files(smoke_run, tmp_path, monkeypatch):
    shutil.copytree(smoke_run / "runs", tmp_path / "runs")
    before = {}
    for path in (tmp_path / PUBLIC).rglob("*"):
        if path.is_file():
            before[path.relative_to(tmp_path / PUBLIC)] = path.read_bytes()
    study = smoke_study(STUDIES[3])
    for relative in (world_folder(study, WORLD) / "world_table.csv", study_folder(study) / "README.md",
                     world_folder(study, WORLD) / "figures/W2-signalling.svg", "sender-studies-summary.png"):
        (tmp_path / PUBLIC / relative).unlink()

    monkeypatch.chdir(tmp_path)
    launch.main(["--all", "--smoke", "--only", "measure,draw", "--jobs", "2"])

    after = {}
    for path in (tmp_path / PUBLIC).rglob("*"):
        if path.is_file():
            after[path.relative_to(tmp_path / PUBLIC)] = path.read_bytes()
    assert after.keys() == before.keys()
    for relative, content in before.items():
        assert after[relative] == content, relative


def test_the_probe_files_can_be_rebuilt_from_the_published_weights(smoke_run, tmp_path, monkeypatch):
    shutil.copytree(smoke_run / "runs", tmp_path / "runs")
    before = {}
    for path in (tmp_path / PUBLIC).rglob("*"):
        if path.is_file():
            before[path.relative_to(tmp_path / PUBLIC)] = path.read_bytes()
    originals = {}
    for path in (tmp_path / PRIVATE).rglob("*"):
        if path.is_file() and ("probes" in path.parts or path.name == "probe_answers.csv"):
            if not path.name.startswith("done."):
                originals[path.relative_to(tmp_path / PRIVATE)] = path.read_bytes()
            path.unlink()
    assert len(originals) == 4 * (2 * 2 + 2 * 2 * 2)  # per sender study 2 lists, 2 sources, 8 answers

    monkeypatch.chdir(tmp_path)
    regenerate_probes.main(["--smoke", "--jobs", "2"])

    for relative, content in originals.items():
        assert (tmp_path / PRIVATE / relative).read_bytes() == content, relative
    after = {}
    for path in (tmp_path / PUBLIC).rglob("*"):
        if path.is_file():
            after[path.relative_to(tmp_path / PUBLIC)] = path.read_bytes()
    assert after == before

