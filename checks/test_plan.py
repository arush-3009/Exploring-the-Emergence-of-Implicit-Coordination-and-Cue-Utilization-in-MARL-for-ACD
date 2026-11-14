import json

import pytest

from studies import launch
from studies.definitions import A_WAITS_BASELINE, SMOKE, STUDIES
from studies.paths import (
    a_waits_folder,
    arm_folder,
    baseline_folder,
    before_folder,
    control_folder,
    cross_study_files,
    probe_list_file,
    roots,
    study_folder,
    team_folder,
    world_folder,
)
from studies.plan import (
    GROUPS,
    REPOSITORY,
    Job,
    job_id,
    jobs_to_run,
    launch_jobs,
    learning_settings,
    log_file,
    marker,
    other_commit_markers,
    study_jobs,
)

CODE = {"commit": "test", "changed_files": []}
RULE_BASELINES = ("always-wait", "inspect-teacher", "restore-teacher", "random")


def expected_graph(study):

    sender = study.kind == "sender"
    warm = "warm-start" in study.start.values()
    from_study_1 = "study-1-team" in study.start.values()
    graph = {}

    for world in study.worlds:
        rules = set()
        for rule in RULE_BASELINES:
            folder = baseline_folder(study, world, rule)
            graph[job_id(folder, "evaluate")] = set()
            graph[job_id(folder, "measure_evaluation")] = {job_id(folder, "evaluate")}
            rules.add(job_id(folder, "evaluate"))

        for seed in study.seeds:
            probes = job_id(probe_list_file(study, world, seed).parent, f"probe_list-seed{seed}")
            if sender:
                graph[probes] = set(rules)
                for arm in study.arms:
                    graph[probes].add(job_id(before_folder(study, world, arm, seed), "evaluate"))

            for arm in study.arms:
                team = team_folder(study, world, arm, seed)
                initial = set()
                if warm:
                    graph[job_id(team, "warm_start")] = set()
                    initial.add(job_id(team, "warm_start"))
                if from_study_1:
                    initial.add(job_id(team_folder(STUDIES[1], world, "cue-visible", seed), "train"))
                graph[job_id(team, "initial_weights")] = initial

                graph[job_id(team, "train")] = {job_id(team, "initial_weights")}
                graph[job_id(team, "evaluate")] = {job_id(team, "train")}
                if sender:
                    before = before_folder(study, world, arm, seed)
                    graph[job_id(team, "train")].add(probes)
                    graph[job_id(before, "evaluate")] = {job_id(team, "initial_weights")}
                    graph[job_id(before, "probe")] = {job_id(team, "initial_weights"), probes}
                    graph[job_id(before, "measure_evaluation")] = {job_id(before, "evaluate"), job_id(before, "probe")}
                    graph[job_id(team, "probe")] = {job_id(team, "train"), probes}
                    graph[job_id(team, "measure_evaluation")] = {job_id(team, "evaluate"), job_id(team, "probe"),
                                                                 job_id(before, "measure_evaluation")}
                    graph[job_id(team, "training_series")] = {job_id(team, "train")}
                else:
                    graph[job_id(team, "measure_evaluation")] = {job_id(team, "evaluate")}

                if A_WAITS_BASELINE in study.baselines:
                    folder = a_waits_folder(study, world, arm, seed)
                    graph[job_id(folder, "evaluate")] = {job_id(team, "initial_weights")}
                    graph[job_id(folder, "measure_evaluation")] = {job_id(folder, "evaluate")}

                if arm == "cue-visible":
                    for control in study.controls:
                        folder = control_folder(study, world, control, seed)
                        graph[job_id(folder, "evaluate")] = {job_id(team, "train")}
                        graph[job_id(folder, "measure_evaluation")] = {job_id(folder, "evaluate")}
                        graph[job_id(folder, "measure_control")] = {job_id(team, "measure_evaluation"),
                                                                    job_id(folder, "measure_evaluation")}

        here = world_folder(study, world)
        world_needs = set()
        for rule in RULE_BASELINES:
            world_needs.add(job_id(baseline_folder(study, world, rule), "measure_evaluation"))
        for arm in study.arms:
            arm_needs = set()
            for seed in study.seeds:
                team = team_folder(study, world, arm, seed)
                arm_needs.update({job_id(team, "train"), job_id(team, "measure_evaluation")})
                if sender:
                    arm_needs.add(job_id(team, "training_series"))
                if arm == "cue-visible":
                    for control in study.controls:
                        arm_needs.add(job_id(control_folder(study, world, control, seed), "measure_control"))
                if A_WAITS_BASELINE in study.baselines:
                    world_needs.add(job_id(a_waits_folder(study, world, arm, seed), "measure_evaluation"))
            graph[job_id(arm_folder(study, world, arm), "measure_arm")] = arm_needs
            world_needs.add(job_id(arm_folder(study, world, arm), "measure_arm"))
        graph[job_id(here, "measure_world")] = world_needs
        graph[job_id(here, "draw_world")] = {job_id(here, "measure_world")}
        graph[job_id(here, "handpicked")] = {job_id(here, "measure_world")}

    here = study_folder(study)
    worlds = set()
    readme_needs = {job_id(here, "measure_study"), job_id(here, "draw_study")}
    for world in study.worlds:
        worlds.add(job_id(world_folder(study, world), "measure_world"))
        readme_needs.add(job_id(world_folder(study, world), "draw_world"))
        readme_needs.add(job_id(world_folder(study, world), "handpicked"))
    graph[job_id(here, "measure_study")] = worlds
    graph[job_id(here, "draw_study")] = set(worlds)
    graph[job_id(here, "write_readmes")] = readme_needs
    return graph


def graph_of(jobs):
    graph = {}
    for job in jobs:
        graph[job.id] = set(job.needs)
        name = job.id.rsplit("/", 1)[1]
        assert job.kind == ("probe_list" if name.startswith("probe_list-seed") else name)
    return graph


@pytest.mark.parametrize("number", sorted(STUDIES))
def test_each_study_s_graph_is_written_out_job_by_job(number, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    study = STUDIES[number]
    graph = graph_of(study_jobs(study, False, CODE))
    assert graph == expected_graph(study)

    counts = {1: 468, 2: 743, 3: 793, 4: 843, 5: 793}
    assert len(graph) == counts[number]


def test_each_world_s_handpicked_job_is_given_its_list_and_every_evaluation_folder():
    study = STUDIES[3]
    _, private = roots(False)
    handpicked = 0
    for job in study_jobs(study, False, CODE):
        if job.kind == "handpicked" and "/two-false-warnings/" in job.id:
            assert job.work.args[0] == private / world_folder(study, "two-false-warnings") / "handpicked.toml"
            assert len(job.work.args[1]) == 44
            assert "training-arms/cue-visible/teams/seed4-team/before" in job.work.args[1]
            assert "baselines/a-waits-with-fixed-b/cue-hidden-failures-suppressed/seed2" in job.work.args[1]
            assert "controls/cue-hidden-unknown-at-evaluation/seed0-team" in job.work.args[1]
            handpicked += 1
    assert handpicked == 1


def test_the_cross_study_jobs_come_only_with_all_four_sender_studies(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    measured = set()
    for number in (2, 3, 4, 5):
        measured.add(job_id(study_folder(STUDIES[number]), "measure_study"))

    graph = graph_of(launch_jobs(list(STUDIES), False, CODE))
    assert graph["./measure_cross_study"] == measured
    assert graph["./draw_cross_study"] == {"./measure_cross_study"}
    assert graph_of(launch_jobs([2, 3, 4, 5], False, CODE))["./measure_cross_study"] == measured
    for numbers in ([1], [2, 3, 4], [3, 4, 5, 1]):
        assert "./measure_cross_study" not in graph_of(launch_jobs(numbers, False, CODE))

    _, private = roots(False)
    assert str(marker(private, "./measure_cross_study")) == "runs/done.measure_cross_study.json"
    assert str(log_file(private, "./draw_cross_study")) == "runs/logs/draw_cross_study.log"


def test_the_groups_hold_every_job_that_reads_records_or_tables_and_nothing_that_plays(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    kinds = set()
    for job in launch_jobs(list(STUDIES), False, CODE):
        kinds.add(job.kind)
    rebuilt = set(GROUPS["measure"]) | set(GROUPS["draw"])
    assert kinds - rebuilt == {"warm_start", "initial_weights", "train", "evaluate", "probe_list", "probe"}
    assert rebuilt <= kinds


def test_the_joined_graph_has_every_need_and_no_cycle():
    graph = launch_jobs(list(STUDIES), False, CODE)
    ids = set()
    for job in graph:
        ids.add(job.id)

    done = set()
    remaining = list(graph)
    while remaining:
        ready = []
        for job in remaining:
            for need in job.needs:
                assert need in ids
            if set(job.needs) <= done:
                ready.append(job)
        assert ready, "the graph has a cycle"
        for job in ready:
            done.add(job.id)
            remaining.remove(job)


def test_one_study_alone_needs_only_study_1_s_trained_cue_visible_teams():
    for number in (3, 4, 5):
        graph = launch_jobs([number], False, CODE)
        ids = set()
        for job in graph:
            ids.add(job.id)
        outside = set()
        for job in graph:
            for need in job.needs:
                if need not in ids:
                    outside.add(need)
        expected = set()
        for world in STUDIES[number].worlds:
            for seed in STUDIES[number].seeds:
                expected.add(job_id(team_folder(STUDIES[1], world, "cue-visible", seed), "train"))
        assert outside == expected
    for number in (1, 2):
        graph = launch_jobs([number], False, CODE)
        ids = set()
        for job in graph:
            ids.add(job.id)
        for job in graph:
            assert set(job.needs) <= ids


def test_smoke_sizes():
    for job in study_jobs(STUDIES[2], True, CODE):
        assert f"/worlds/{SMOKE['world']}/" in job.id or job.kind in ("measure_study", "draw_study", "write_readmes")
        if job.kind == "evaluate":
            assert job.work.args[2:4] == ((2001, 2002), 10)
    seeds = set()
    for job in study_jobs(STUDIES[2], True, CODE):
        if job.kind == "train":
            seeds.add(job.work.args[2])
    assert seeds == {0, 1}

    training, imitation = learning_settings(STUDIES[4], True)
    assert training["training"] == {"iterations": 3, "episodes_per_iteration": 4}
    assert imitation["teacher"] == {"rule": "inspect-then-restore-prob-restore-weakened", "episodes": 20}
    assert imitation["actor_fit"]["restore_target_weight"] == 0.6
    assert training["fixed_defenders"] == {"B": "greedy"}
    training, imitation = learning_settings(STUDIES[2], False)
    assert "fixed_defenders" not in training
    assert training["training"] == {"iterations": 3000, "episodes_per_iteration": 16}
    assert "restore_target_weight" not in imitation["actor_fit"]
    assert STUDIES[2].defender_imitation_overrides == {"A": {"actor_fit.restore_target_weight": 0.6}}


def test_the_full_smoke_has_every_job_of_the_real_launch_at_smoke_sizes():
    real = graph_of(launch_jobs(list(STUDIES), False, CODE))
    full = graph_of(launch_jobs(list(STUDIES), True, CODE, True))
    assert full == real
    for job in launch_jobs(list(STUDIES), True, CODE, True):
        if job.kind == "evaluate":
            assert job.work.args[2:4] == ((2001, 2002), 10)
            assert job.work.args[4].parts[:2] == ("runs", "full-smoke")
        if job.kind == "train":
            assert job.work.args[1]["training"] == {"iterations": 3, "episodes_per_iteration": 4}


def test_markers_and_logs_sit_in_the_private_mirror():
    _, private = roots(False)
    team = "study-1-receiver-cue-utilization/worlds/reliable-warnings/training-arms/cue-visible/teams/seed0-team"
    assert str(marker(private, f"{team}/train")) == f"runs/{team}/done.train.json"
    probes = "study-2-sender-joint-teacher-start/worlds/reliable-warnings/probes"
    assert str(marker(private, f"{probes}/probe_list-seed3")) == f"runs/{probes}/done.probe_list-seed3.json"
    assert str(log_file(private, f"{team}/train")) == (
        "runs/logs/study-1-receiver-cue-utilization/"
        "worlds.reliable-warnings.training-arms.cue-visible.teams.seed0-team.train.log")


def fake_graph():
    return [Job("s/a/evaluate", "evaluate", (), None),
            Job("s/a/measure_evaluation", "measure_evaluation", ("s/a/evaluate",), None),
            Job("s/b/train", "train", ("s/x/train",), None),
            Job("s/b/evaluate", "evaluate", ("s/b/train",), None),
            Job("s/b/measure_evaluation", "measure_evaluation", ("s/b/evaluate",), None)]


def ids_of(jobs):
    ids = []
    for job in jobs:
        ids.append(job.id)
    return ids


def done(private, *ids):
    for id in ids:
        marker(private, id).parent.mkdir(parents=True, exist_ok=True)
        marker(private, id).write_text("{}")


def test_which_jobs_a_launch_runs(tmp_path):
    graph = fake_graph()

    run, missing = jobs_to_run(graph, tmp_path, None, False)
    assert ids_of(run) == ids_of(graph)
    assert missing == ["s/x/train"]

    done(tmp_path, "s/x/train", "s/a/evaluate", "s/a/measure_evaluation", "s/b/train", "s/b/measure_evaluation")
    run, missing = jobs_to_run(graph, tmp_path, None, False)
    assert ids_of(run) == ["s/b/evaluate", "s/b/measure_evaluation"]
    assert missing == []

    run, missing = jobs_to_run(graph, tmp_path, None, True)
    assert ids_of(run) == ids_of(graph)

    run, missing = jobs_to_run(graph, tmp_path, ["measure"], False)
    assert ids_of(run) == ["s/a/measure_evaluation", "s/b/measure_evaluation"]
    assert missing == ["s/b/evaluate"]
    done(tmp_path, "s/b/evaluate")
    run, missing = jobs_to_run(graph, tmp_path, ["measure"], True)
    assert ids_of(run) == ["s/a/measure_evaluation", "s/b/measure_evaluation"]
    assert missing == []

    run, missing = jobs_to_run(graph, tmp_path, ["draw"], False)
    assert run == []


def test_the_launcher_refuses_what_it_cannot_do(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    with pytest.raises(SystemExit):
        launch.main(["--all"])
    assert "repository root" in capsys.readouterr().err
    with pytest.raises(SystemExit):
        launch.main(["--all", "--smoke", "--only", "figures"])
    assert "--only takes measure, draw" in capsys.readouterr().err
    with pytest.raises(SystemExit, match="its marker is missing: runs/smoke/runs/study-1-receiver-cue-utilization/"):
        launch.main(["--study", "3", "--smoke"])
    assert not (tmp_path / "runs").exists()


def test_check_reports_what_the_launch_would_refuse_and_launches_nothing(monkeypatch, capsys, tmp_path):
    # an empty folder stands in for runs/ so real markers cannot change the check
    monkeypatch.chdir(REPOSITORY)

    def empty_roots(smoke, full=False):
        return tmp_path / "experiment-runs", tmp_path / "runs"

    monkeypatch.setattr(launch, "roots", empty_roots)
    monkeypatch.setattr("studies.plan.roots", empty_roots)
    with pytest.raises(SystemExit, match="the launch would refuse"):
        launch.main(["--study", "3", "--check"])
    output = capsys.readouterr().out
    assert "793 jobs" in output
    assert "studies/settings/ holds the values of studies/definitions.py" in output
    assert f"its marker is missing: {tmp_path / 'runs'}/study-1-receiver-cue-utilization/" in output
    assert not (tmp_path / "runs").exists()


def test_a_resumed_launch_refuses_markers_of_another_commit(tmp_path):
    graph = fake_graph()
    for id, commit in (("s/x/train", "one"), ("s/a/evaluate", "one"), ("s/a/measure_evaluation", "one"),
                       ("s/b/train", "two")):
        marker(tmp_path, id).parent.mkdir(parents=True, exist_ok=True)
        marker(tmp_path, id).write_text(json.dumps({"code": {"commit": commit}}))
    run, missing = jobs_to_run(graph, tmp_path, None, False)
    assert ids_of(run) == ["s/b/evaluate", "s/b/measure_evaluation"]
    assert missing == []
    assert other_commit_markers(graph, run, tmp_path, "one") == [marker(tmp_path, "s/b/train")]
    assert other_commit_markers(graph, run, tmp_path, "two") == [marker(tmp_path, "s/a/evaluate"),
                                                                 marker(tmp_path, "s/a/measure_evaluation"),
                                                                 marker(tmp_path, "s/x/train")]


def test_a_launch_removes_the_markers_of_what_it_runs_before_it_starts(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _, private = roots(True)
    graph = launch_jobs([1], True, CODE)
    for job in graph:
        done(private, job.id)

    started = []

    def stopped(works, needs, logs, workers):
        started.append(set(works))
        raise RuntimeError("stopped before the first job")

    monkeypatch.setattr(launch, "run_jobs", stopped)
    with pytest.raises(RuntimeError, match="stopped before the first job"):
        launch.main(["--study", "1", "--smoke", "--only", "measure"])

    rebuilt = set(GROUPS["measure"]) | set(GROUPS["draw"])
    measuring = set()
    for job in graph:
        if job.kind in rebuilt:
            measuring.add(job.id)
        assert marker(private, job.id).exists() == (job.kind not in rebuilt)
    assert started == [measuring]


def test_one_sender_study_measured_again_removes_the_summary_of_the_four(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    public, private = roots(True)
    graph = launch_jobs(list(STUDIES), True, CODE)
    for job in graph:
        done(private, job.id)
    public.mkdir(parents=True)
    for path in cross_study_files():
        (public / path).write_text("the four studies as they were")

    monkeypatch.setattr(launch, "run_jobs", lambda works, needs, logs, workers: None)
    for arguments in (["--study", "1", "--smoke", "--only", "measure"], ["--all", "--smoke", "--only", "measure"]):
        launch.main(arguments)
        for path in cross_study_files():
            assert (public / path).exists()
    launch.main(["--study", "3", "--smoke", "--only", "measure"])
    for path in cross_study_files():
        assert not (public / path).exists()
    assert not marker(private, "./measure_cross_study").exists()
    assert not marker(private, "./draw_cross_study").exists()
