# Command to launch experiment.

# uv run --locked python -m studies.launch --all --jobs 32
# uv run --locked python -m studies.launch --study 3 --jobs 8
# uv run --locked python -m studies.launch --all --jobs 8 --only measure,draw
# uv run --locked python -m studies.launch --all --smoke
# uv run --locked python -m studies.launch --all --full-smoke --jobs 8
# uv run --locked python -m studies.launch --all --check


import argparse
import subprocess
from functools import partial
from pathlib import Path

from learning.imitation_config import read_imitation_config
from learning.training_config import read_training_config
from studies.definitions import IMITATION_SETTINGS, STUDIES, TRAINING_SETTINGS
from studies.parallel import run_jobs
from studies.paths import cross_study_files, roots
from studies.plan import (
    GROUPS,
    REPOSITORY,
    execute,
    jobs_to_run,
    launch_jobs,
    log_file,
    marker,
    other_commit_markers,
)


def git(*arguments: str) -> str:
    return subprocess.run(["git", "--no-optional-locks", *arguments], 
                          cwd=REPOSITORY, check=True,
                          capture_output=True, 
                          text=True).stdout



def code_version() -> dict:

    changes = git("status", "--porcelain", "--", ".", ":(exclude)experiment-runs", ":(exclude)runs")
    
    changed_files = []
    for line in changes.splitlines():
        changed_files.append(line[3:])

    return {"commit": git("rev-parse", "HEAD").strip(), "changed_files": changed_files}


def settings_match_definitions() -> bool:
    training = read_training_config(REPOSITORY / "studies/settings/training_config.toml")
    imitation = read_imitation_config(REPOSITORY / "studies/settings/imitation_config.toml")
    return training == TRAINING_SETTINGS and imitation == IMITATION_SETTINGS


def main(arguments: list[str] | None = None) -> None:

    parser = argparse.ArgumentParser(description="Run experiment studies.")
    which = parser.add_mutually_exclusive_group(required=True)
    which.add_argument("--all", action="store_true", help="all five studies in one job graph")
    which.add_argument("--study", type=int, choices=sorted(STUDIES), help="one study")
    parser.add_argument("--jobs", type=int, default=1, help="how many jobs run at once (default 1)")
    parser.add_argument("--only", help=f"run again the jobs of these groups, comma-separated: {', '.join(GROUPS)}")
    sizes = parser.add_mutually_exclusive_group()
    sizes.add_argument("--smoke", action="store_true", help="tiny sizes, one world and two seeds, everything under runs/smoke/")
    sizes.add_argument("--full-smoke", action="store_true",
                       help="tiny sizes with every world and seed of the real launch, everything under runs/full-smoke/")
    parser.add_argument("--check", action="store_true", help="validate settings, sources and dependencies, launch nothing")
    
    
    options = parser.parse_args(arguments)
    
    only = None
    
    if options.only is not None:
        only = options.only.split(",")
        for group in only:
            if group not in GROUPS:
                parser.error(f"--only takes {', '.join(GROUPS)}, not {group!r}")
                
    if options.jobs < 1:
        parser.error("--jobs must be at least 1")
        

    smoke = options.smoke or options.full_smoke
    full = options.full_smoke

    if not smoke and Path.cwd().resolve() != REPOSITORY:
        parser.error(f"a launch that is not --smoke runs from the repository root, {REPOSITORY}")


    numbers = list(STUDIES) if options.all else [options.study]
    code = code_version()
    graph = launch_jobs(numbers, smoke, code, full)
    _, private = roots(smoke, full)
    run, missing = jobs_to_run(graph, private, only, smoke)

    #refuse launch
    problems = []
    if not settings_match_definitions():
        problems.append("studies/settings/ does not hold the values of studies/definitions.py")
    for need in missing:
        problems.append(f"a job this launch needs is not done, its marker is missing: {marker(private, need)}")
    if not smoke and only is None:
        for file in other_commit_markers(graph, run, private, code["commit"]):
            problems.append(f"a marker names another commit than {code['commit']}: {file}")
    if not smoke and code["changed_files"]:
        problems.append("the code has uncommitted changes, and every run.json must name one clean commit: "
                        + ", ".join(code["changed_files"]))

    if options.check:
        counts = {}
        for job in graph:
            counts[job.kind] = counts.get(job.kind, 0) + 1
        print(f"studies {numbers}: {len(graph)} jobs, of which this launch would run {len(run)}")
        for kind, count in counts.items():
            print(f"  {kind}: {count}")
        if settings_match_definitions():
            print("studies/settings/ holds the values of studies/definitions.py")
        print(f"code: {code['commit']}")
        for problem in problems:
            print(problem)
        if problems:
            raise SystemExit(f"{len(problems)} problems; the launch would refuse to start")
        print("Nothing would stop this launch.")
        return

    if problems:
        raise SystemExit("The launch refuses to start:\n" + "\n".join(problems))

    chosen = set()
    for job in run:
        chosen.add(job.id)
        marker(private, job.id).unlink(missing_ok=True)


    senders = set()
    for study in STUDIES.values():
        if study.kind == "sender":
            senders.add(f"{study.folder}/measure_study")
            
    summarised = False
    for job in graph:
        if job.kind == "measure_cross_study":
            summarised = True
            
    if chosen & senders and not summarised:
        
        public, _ = roots(smoke, full)
        
        for path in cross_study_files():
            (public / path).unlink(missing_ok=True)
            
        for id in ("./measure_cross_study", "./draw_cross_study"):
            marker(private, id).unlink(missing_ok=True)
            
        print(f"Removed {public / 'sender-studies-summary.csv'} and its figure until a launch of all four sender studies makes them again.", flush=True)

    works = {}
    needs = {}
    logs = {}
    for job in run:
        works[job.id] = partial(execute, job.work, marker(private, job.id), job.id, code)
        inside = []
        for need in job.needs:
            if need in chosen:
                inside.append(need)
        needs[job.id] = inside
        logs[job.id] = log_file(private, job.id)

    print(f"{len(run)} jobs to run, {options.jobs} at a time, logs in {private / 'logs'}", flush=True)
    run_jobs(works, needs, logs, options.jobs)
    print("All jobs finished.", flush=True)


if __name__ == "__main__":
    main()
