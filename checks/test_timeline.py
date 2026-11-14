import html
import json
import shutil
import tomllib

import pytest

from episodes.record_io import read_records, read_run_json
from measurements.tables import read_csv
from studies import jobs
from studies.definitions import SMOKE, STUDIES
from studies.paths import baseline_folder, roots, team_folder, world_folder
from studies.plan import smoke_study
from tools import timeline
from tools.timeline import timeline_html

PUBLIC, PRIVATE = roots(True)
WORLD = SMOKE["world"]


def record_of(folder, evaluation_seed, episode):
    for record in read_records(folder / "records.jsonl.gz"):
        if record.evaluation_seed == evaluation_seed and record.episode == episode:
            return record
    raise AssertionError(f"{folder} has no episode {episode} of evaluation seed {evaluation_seed}")


def row_of(path, evaluation_seed, episode):
    for row in read_csv(path):
        if row["evaluation_seed"] == str(evaluation_seed) and row["episode"] == str(episode):
            return row
    raise AssertionError(f"{path} has no episode {episode} of evaluation seed {evaluation_seed}")


def test_each_chosen_episode_is_replayed_into_its_trace_and_pages(smoke_run):
    entries = 0
    folders = 0
    for list_file in sorted((smoke_run / PRIVATE).rglob("handpicked.toml")):
        world = list_file.parent.relative_to(smoke_run / PRIVATE)
        with list_file.open("rb") as file:
            chosen = tomllib.load(file)["timeline"]
        readme = (smoke_run / PUBLIC / world / "README.md").read_text()

        for entry in chosen:
            name = f"episode-{entry['evaluation_seed']}-{entry['episode']:03d}"
            for folder in entry["folders"]:
                public = smoke_run / PUBLIC / world / folder
                record = record_of(smoke_run / PRIVATE / world / folder, entry["evaluation_seed"], entry["episode"])
                trace = json.loads((public / "traces" / f"{name}.json").read_text())
                assert trace == json.loads(json.dumps(record.to_dict()))
                page = (public / "timelines" / f"{name}.html").read_text()
                assert html.escape(entry["reason"]) in page
                assert page.count('<table class="grid">') == 1
                folders += 1

            pages = []
            for path in (smoke_run / PUBLIC / world / "timelines").iterdir():
                if path.name.startswith(f"{name}-"):
                    pages.append(path)
            assert len(pages) == 1
            stacked = pages[0].read_text()
            assert stacked.count('<table class="grid">') == len(entry["folders"])
            assert html.escape(entry["reason"]) in stacked
            assert f"(timelines/{pages[0].name}): {entry['reason']}" in readme
            entries += 1
    assert (entries, folders) == (3, 8)


def test_the_page_shows_the_record_and_the_episode_s_measurements(smoke_run):
    pages = 0
    outages = 0
    for number in (1, 3):
        study = smoke_study(STUDIES[number])
        folder = team_folder(study, WORLD, "cue-visible", 0)
        run = read_run_json(smoke_run / PRIVATE / folder / "run.json")
        for record in read_records(smoke_run / PRIVATE / folder / "records.jsonl.gz"):
            metrics = row_of(smoke_run / PUBLIC / folder / "episodes.csv", record.evaluation_seed, record.episode)
            page = timeline_html(record, run, metrics)
            last = len(record.intervals) - 1

            assert f'title="running total after interval {last}">{float(metrics["reward"]):g}<' in page
            assert page.count('<td class="reward') == len(record.intervals)

            intrusion = record.script["intrusion"]
            assert page.count('<th class="intrusion"') == (0 if intrusion is None else 1)
            assert page.count("&#9733;") == (0 if metrics["b_first_response_interval"] == "" else 1)

            cells = set()
            for outage in record.script["outages"]:
                for t in range(outage["interval"], min(outage["interval"] + outage["duration"], last + 1)):
                    cells.add((outage["server"], t))
            assert page.count('outage" style=') == len(cells)
            outages += len(cells)
            pages += 1
    assert pages == 2 * len(STUDIES[1].evaluation_seeds) * SMOKE["episodes_per_seed"]
    assert outages > 0


def test_the_command_line_writes_the_page_of_one_episode(smoke_run, tmp_path):
    study = smoke_study(STUDIES[1])
    folder = team_folder(study, WORLD, "cue-hidden-unknown", 1)
    episodes = smoke_run / PUBLIC / folder / "episodes.csv"
    out = tmp_path / "page.html"
    timeline.main([str(smoke_run / PRIVATE / folder), "--seed", "2002", "--episode", "4", "--episodes", str(episodes),
                   "--out", str(out)])

    record = record_of(smoke_run / PRIVATE / folder, 2002, 4)
    run = read_run_json(smoke_run / PRIVATE / folder / "run.json")
    assert out.read_text() == timeline_html(record, run, row_of(episodes, 2002, 4))

    with pytest.raises(SystemExit):
        timeline.main([str(smoke_run / PRIVATE / folder), "--seed", "2002", "--episode", "99"])


def copy_world(smoke_run, study, tmp_path):
    public = tmp_path / "public"
    private = tmp_path / "private"
    shutil.copytree(smoke_run / PUBLIC / world_folder(study, WORLD), public)
    shutil.copytree(smoke_run / PRIVATE / world_folder(study, WORLD), private)
    return public, private


def test_the_job_writes_every_page_again_and_keeps_none_of_an_old_list(smoke_run, tmp_path, monkeypatch):
    # run.json names the weights relative to the launch folder
    monkeypatch.chdir(smoke_run)
    study = smoke_study(STUDIES[1])
    public, private = copy_world(smoke_run, study, tmp_path)
    old = public / "baselines/random/timelines/episode-2001-001.html"
    old.parent.mkdir(parents=True)
    old.write_text("an episode taken off the list")
    (public / "timelines/episode-2001-001-random.html").write_text("an episode taken off the list")

    list_file = private / "handpicked.toml"
    folders = ["training-arms/cue-visible/teams/seed0-team", "training-arms/cue-hidden-unknown/teams/seed0-team",
               "controls/cue-hidden-unknown-at-evaluation/seed1-team", "baselines/always-wait", "baselines/random"]
    jobs.handpicked(list_file, folders, public, private, public / "baselines/always-wait")

    assert not old.exists()
    assert not (public / "baselines/random/timelines").exists()
    assert not (public / "timelines/episode-2001-001-random.html").exists()
    for name in ("episode-2001-003-cue-visible-seed0__cue-hidden-unknown-seed0.html",
                 "episode-2002-007-cue-hidden-unknown-at-evaluation-seed1__always-wait.html"):
        assert (public / "timelines" / name).read_bytes() == (
            smoke_run / PUBLIC / world_folder(study, WORLD) / "timelines" / name).read_bytes()


def test_an_episode_that_replays_differently_is_refused(smoke_run, tmp_path):
    study = smoke_study(STUDIES[1])
    public, private = copy_world(smoke_run, study, tmp_path)
    relative = baseline_folder(study, WORLD, "always-wait").relative_to(world_folder(study, WORLD)).as_posix()

    run = json.loads((private / relative / "run.json").read_text())
    for defender in ("A", "B"):
        run["policies"][defender] = {"type": "rule", "rule": "inspect-teacher"}
    (private / relative / "run.json").write_text(json.dumps(run))

    list_file = tmp_path / "handpicked.toml"
    list_file.write_text(f'[[timeline]]\nevaluation_seed = 2001\nepisode = 3\nfolders = ["{relative}"]\n'
                         'reason = "The always-wait baseline."\n')
    with pytest.raises(AssertionError, match="replays differently"):
        jobs.handpicked(list_file, [relative], public, private, public / relative)


def test_a_list_with_a_mistake_is_refused_before_any_page_is_removed(smoke_run, tmp_path):
    study = smoke_study(STUDIES[1])
    public, private = copy_world(smoke_run, study, tmp_path)
    pages = sorted((public / "timelines").iterdir())
    folders = ["baselines/always-wait", "baselines/random"]
    entry = '[[timeline]]\nevaluation_seed = 2001\nepisode = 3\nfolders = ["baselines/random"]\n'
    list_file = tmp_path / "handpicked.toml"

    for text, message in ((entry, "evaluation_seed, episode, folders and reason"),
                          (entry + 'reason = "A random team."\n' + entry + 'reason = "Again."\n', "the same episode"),
                          (entry.replace("random", "inspect-teacher") + 'reason = "A teacher."\n',
                           "is not an evaluation folder of this world")):
        list_file.write_text(text)
        with pytest.raises(ValueError, match=message):
            jobs.handpicked(list_file, folders, public, private, public / "baselines/always-wait")
        assert sorted((public / "timelines").iterdir()) == pages


def test_an_episode_two_entries_show_is_one_page_with_both_reasons(smoke_run, tmp_path):
    study = smoke_study(STUDIES[1])
    public, private = copy_world(smoke_run, study, tmp_path)
    list_file = tmp_path / "handpicked.toml"
    list_file.write_text('[[timeline]]\nevaluation_seed = 2002\nepisode = 5\nfolders = ["baselines/random"]\n'
                         'reason = "The random baseline alone."\n'
                         '[[timeline]]\nevaluation_seed = 2002\nepisode = 5\n'
                         'folders = ["baselines/random", "baselines/always-wait"]\n'
                         'reason = "The random baseline beside always-wait."\n')
    folders = ["baselines/always-wait", "baselines/random"]
    jobs.handpicked(list_file, folders, public, private, public / "baselines/always-wait")

    page = (public / "baselines/random/timelines/episode-2002-005.html").read_text()
    assert "The random baseline alone. The random baseline beside always-wait." in page
    names = []
    for path in (public / "timelines").iterdir():
        names.append(path.name)
    assert sorted(names) == ["episode-2002-005-random.html", "episode-2002-005-random__always-wait.html"]
