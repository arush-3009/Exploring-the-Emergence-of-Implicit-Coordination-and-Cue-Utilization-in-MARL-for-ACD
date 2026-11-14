# Rebuild the sender studies' probe lists and probe answers from the weights, without training.
#
# uv run --locked python -m studies.regenerate_probes --jobs 8
#
# This command plays the six source evaluations of every sender 
# seed (the initial team under each arm's mask and the four
# rule baselines), builds the lists and tests them on A, all into `runs/`. It uses
# the launcher's own jobs and writes the usual markers and logs.

import argparse
from functools import partial
from pathlib import Path

from studies.definitions import STUDIES
from studies.launch import code_version
from studies.parallel import run_jobs
from studies.paths import roots, team_folder
from studies.plan import REPOSITORY, execute, launch_jobs, log_file, marker, smoke_study


def probe_jobs(graph: list) -> list:

    chosen = []
    for job in graph:
        source = job.kind == "evaluate" and ("/before/" in job.id or "/baselines/" in job.id)
        if job.kind in ("probe_list", "probe") or source:
            chosen.append(job)
            
    return chosen


def main(arguments: list[str] | None = None) -> None:

    parser = argparse.ArgumentParser(description="Rebuild the probe lists and answers from the published weights.")
    parser.add_argument("--jobs", type=int, default=1, help="how many jobs run at once (default 1)")
    sizes = parser.add_mutually_exclusive_group()
    sizes.add_argument("--smoke", action="store_true", help="the smoke run under runs/smoke/")
    sizes.add_argument("--full-smoke", action="store_true", help="the full smoke run under runs/full-smoke/")
    options = parser.parse_args(arguments)

    smoke = options.smoke or options.full_smoke
    full = options.full_smoke

    if not smoke and Path.cwd().resolve() != REPOSITORY:
        parser.error(f"a run that is not --smoke starts from the repository root, {REPOSITORY}")

    code = code_version()
    if not smoke and code["changed_files"]:
        raise SystemExit("the code has uncommitted changes, and every run.json must name one clean commit: "
                         + ", ".join(code["changed_files"]))

    senders = []
    for number, study in STUDIES.items():
        if study.kind == "sender":
            senders.append(number)

    public, private = roots(smoke, full)
    graph = launch_jobs(senders, smoke, code, full)
    chosen = probe_jobs(graph)

    # every weights file the chosen jobs read must be there
    for number in senders:
        study = STUDIES[number]
        if smoke:
            study = smoke_study(study, full)
        for world in study.worlds:
            for arm in study.arms:
                for seed in study.seeds:
                    team = public / team_folder(study, world, arm, seed)
                    for name in ("weights/initial.pt", "weights/final.pt"):
                        if not (team / name).exists():
                            raise SystemExit(f"missing {team / name}; the published weights are needed")

    ids = set()
    for job in chosen:
        ids.add(job.id)

    works = {}
    needs = {}
    logs = {}
    for job in chosen:
        marker(private, job.id).unlink(missing_ok=True)
        works[job.id] = partial(execute, job.work, marker(private, job.id), job.id, code)
        inside = []
        for need in job.needs:
            if need in ids:
                inside.append(need)
        needs[job.id] = inside
        logs[job.id] = log_file(private, job.id)

    print(f"{len(chosen)} jobs to run, {options.jobs} at a time, logs in {private / 'logs'}", flush=True)
    run_jobs(works, needs, logs, options.jobs)
    print(f"The probe lists, their sources and the answers are under {private}.", flush=True)


if __name__ == "__main__":
    main()
