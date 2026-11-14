import random
from dataclasses import dataclass, replace
from functools import partial
from pathlib import Path

from episodes.record_io import read_run_json, write_run_json
from learning.imitation_config import read_imitation_config, validate_imitation_config
from learning.training_config import read_training_config, validate_training_config
from studies import jobs
from studies.definitions import (
    A_WAITS_BASELINE,
    CONTROLS,
    SMOKE,
    STUDIES,
    Study,
    apply_dotted_overrides,
)
from studies.paths import (
    a_waits_folder,
    arm_folder,
    baseline_folder,
    before_folder,
    control_folder,
    figure_names,
    probe_answers_file,
    probe_list_file,
    probe_sources_file,
    roots,
    study_folder,
    team_folder,
    world_folder,
)
from world.settings import apply_overrides, load_world_settings

REPOSITORY = Path(__file__).resolve().parents[1]


GROUPS = {"measure": ("measure_evaluation",
                      "measure_control", 
                      "training_series",
                      "measure_arm", 
                      "measure_world",
                      "measure_study",
                      "measure_cross_study"),
          
          "draw": ("draw_world", 
                   "draw_study",
                   "draw_cross_study",
                   "write_readmes", 
                   "handpicked")}



@dataclass(frozen=True)
class Job:
    id: str
    kind: str
    needs: tuple  # the ids of the jobs whose outputs it reads
    work: partial  # a function of studies/jobs.py with every argument given


def job_id(folder: Path, name: str) -> str:
    return f"{folder.as_posix()}/{name}"


def marker(private: Path, id: str) -> Path:
    folder, name = id.rsplit("/", 1)
    return private / folder / f"done.{name}.json"


def log_file(private: Path, id: str) -> Path:
    study, rest = id.split("/", 1)
    return private / "logs" / study / f"{rest.replace('/', '.')}.log"


def probe_list_id(study: Study, world: str, seed: int) -> str:
    return job_id(probe_list_file(study, world, seed).parent, f"probe_list-seed{seed}")



def execute(work: partial, marker_file: Path, id: str, code: dict) -> None:
    started = jobs.now()
    work()
    write_run_json(marker_file, {"job": id, "code": code, "started": started, "finished": jobs.now()})


def world_settings(study: Study, world: str, masks: list[dict]) -> dict:

    overrides = dict(study.world_overrides)
    for mask in masks:
        overrides.update(mask)

    return apply_overrides(load_world_settings(REPOSITORY / "worlds" / world), overrides)


def learning_settings(study: Study, smoke: bool) -> tuple[dict, dict]:

    training = read_training_config(REPOSITORY / "studies/settings/training_config.toml")
    imitation = read_imitation_config(REPOSITORY / "studies/settings/imitation_config.toml")

    tables = {"training": training, "imitation": imitation}
    apply_dotted_overrides(tables, study.training_overrides)

    fixed = {}
    
    for defender in study.fixed:
        fixed[defender] = "greedy"
        
    if fixed:
        training["fixed_defenders"] = fixed

    if smoke:
        training["training"]["iterations"] = SMOKE["iterations"]
        training["training"]["episodes_per_iteration"] = SMOKE["episodes_per_iteration"]
        imitation["teacher"]["episodes"] = SMOKE["teacher_episodes"]

    validate_training_config(training)
    validate_imitation_config(imitation)

    return training, imitation



def smoke_study(study: Study, full: bool = False) -> Study:
    if full:
        return replace(study, episodes_per_seed=SMOKE["episodes_per_seed"])

    return replace(study, worlds=(SMOKE["world"],), seeds=SMOKE["seeds"], episodes_per_seed=SMOKE["episodes_per_seed"])


def greedy_actor(weights: Path, hidden_sizes: list) -> dict:
    return {"type": "greedy-actor", "weights": weights.as_posix(), "hidden_sizes": hidden_sizes}


def rule(name: str) -> dict:
    return {"type": "rule", "rule": name}


def study_jobs(study: Study, smoke: bool, code: dict, full: bool = False) -> list[Job]:

    public, private = roots(smoke, full)
    if smoke:
        study = smoke_study(study, full)

    training, imitation = learning_settings(study, smoke)
    hidden_sizes = training["networks"]["hidden_sizes"]
    sender = study.kind == "sender"
    seeds = study.evaluation_seeds
    episodes = study.episodes_per_seed
    
    result = []

    def add(folder: Path, 
            name: str, 
            kind: str, 
            needs: list, 
            function, 
            *arguments) -> None:
        result.append(Job(job_id(folder, name), kind, tuple(needs), partial(function, *arguments)))

    def measured(folder: Path, 
                 needs: list, 
                 summarise: bool, 
                 probe_list: Path | None, 
                 probe_answers: Path | None,
                 before: Path | None) -> None:
        add(folder, 
            "measure_evaluation",
            "measure_evaluation", 
            needs, 
            jobs.measure_evaluation,
            private / folder / "records.jsonl.gz", 
            world_config, 
            sender,
            seeds, 
            public / folder, 
            summarise, 
            probe_list,
            probe_answers,
            before)

    worlds = {}
    lists = {}

    for world in study.worlds:

        plain = world_settings(study, world, [])
        world_config = plain["world"]

        rule_folders = []
        
        for name in study.baselines:
            
            if name == A_WAITS_BASELINE:
                continue
            
            folder = baseline_folder(study, world, name)
            labels = {"kind": "baseline", "study": study.folder, "world": world, "rule": name}
            
            add(folder, 
                "evaluate",
                "evaluate", 
                [], 
                jobs.evaluate,
                {"A": rule(name), "B": rule(name)},
                plain, 
                seeds,
                episodes, 
                private / folder, 
                labels, 
                code)
            
            measured(folder, [job_id(folder, "evaluate")], True, None, None, None)
            rule_folders.append(folder)


        for arm, mask in study.arms.items():

            settings = world_settings(study, world, [mask])
            mask_name = arm if mask else None

            for seed in study.seeds:

                team = team_folder(study, world, arm, seed)
                labels = {"study": study.folder, "world": world, "arm": arm, "seed": seed}
                initial = public / team / "weights/initial.pt"
                final = public / team / "weights/final.pt"
                source = team_folder(STUDIES[1], world, "cue-visible", seed)
                source_weights = public / source / "weights/final.pt"

                starts = {}
                fit = []
                initial_needs = []
                
                for defender in ("A", "B"):
                    
                    start = study.start[defender]
                    
                    if start == "warm-start":
                        
                        starts[defender] = {"start": start,
                                            "weights": private / team / "weights/warm_start.pt",
                                            "info": private / team / "warm_start.json"}
                        
                        fit.append(defender)
                        
                        
                    elif start == "study-1-team":
                        starts[defender] = {"start": start, "weights": source_weights}
                        if job_id(source, "train") not in initial_needs:
                            initial_needs.append(job_id(source, "train"))
                            
                            
                    elif start == "random":
                        starts[defender] = {"start": start}
                        
                        
                    else:
                        raise ValueError(f"study {study.number}: unknown start {start!r} for {defender}")

                if fit:
                    add(team, 
                        "warm_start", 
                        "warm_start", 
                        [], 
                        jobs.warm_start,
                        settings, 
                        training, 
                        imitation,
                        seed, 
                        tuple(fit),
                        study.defender_imitation_overrides,
                        private / team,
                        code)
                    
                    initial_needs.append(job_id(team, "warm_start"))
                    
                    
                add(team, 
                    "initial_weights", 
                    "initial_weights", 
                    initial_needs,
                    jobs.initial_weights,
                    starts, 
                    settings, 
                    training, 
                    seed, 
                    public / team, 
                    private / team, 
                    code)


                train_needs = [job_id(team, "initial_weights")]
                
                probe_file = None
                world_seed = None
                
                if sender:
                    probe_file = private / probe_list_file(study, world, seed)
                    train_needs.append(probe_list_id(study, world, seed))
                    world_seed = random.Random(seed + 10000 * study.number).randrange(2**31)
                    
                    
                fixed_source = None
                if study.fixed:
                    fixed_source = source_weights
                add(team, "train", "train", train_needs, jobs.train,
                    settings, training, seed, world_seed, sender, initial, fixed_source, probe_file, public / team,
                    private / team, labels, code)


                team_policies = {"A": greedy_actor(final, hidden_sizes), "B": greedy_actor(final, hidden_sizes)}
                add(team, 
                    "evaluate",
                    "evaluate", 
                    [job_id(team, "train")],
                    jobs.evaluate,
                    team_policies,
                    settings, 
                    seeds,
                    episodes,
                    private / team,
                    {"kind": "team-evaluation", **labels, "mask": mask_name}, 
                    code)


                if sender:
                    
                    before = before_folder(study, world, arm, seed)
                    
                    add(before, "evaluate", "evaluate", [job_id(team, "initial_weights")], jobs.evaluate,
                        {"A": greedy_actor(initial, hidden_sizes), "B": greedy_actor(initial, hidden_sizes)},
                        settings, seeds, episodes, private / before,
                        {"kind": "before-evaluation", **labels, "mask": mask_name}, code)
                    
                    
                    add(before, "probe", "probe", [job_id(team, "initial_weights"), probe_list_id(study, world, seed)],
                        jobs.probe, initial, settings, hidden_sizes, probe_file, private / probe_answers_file(before))
                    
                    measured(before, [job_id(before, "evaluate"), job_id(before, "probe")], True, probe_file,
                             private / probe_answers_file(before), None)

                    add(team, "probe", "probe", [job_id(team, "train"), probe_list_id(study, world, seed)],
                        jobs.probe, final, settings, hidden_sizes, probe_file, private / probe_answers_file(team))
                    
                    measured(team, [job_id(team, "evaluate"), job_id(team, "probe"),
                                    job_id(before, "measure_evaluation")], True, probe_file,
                             private / probe_answers_file(team), public / before)
                    
                    add(team, "training_series", "training_series", [job_id(team, "train")], jobs.training_series,
                        private / team / "training/training_episodes.csv", public / team / "training_behaviour.csv")
                    
                    
                else:
                    measured(team, [job_id(team, "evaluate")], True, None, None, None)

                if A_WAITS_BASELINE in study.baselines:
                    
                    folder = a_waits_folder(study, world, arm, seed)
                    
                    add(folder, "evaluate", "evaluate", [job_id(team, "initial_weights")], jobs.evaluate,
                        {"A": rule("always-wait"), "B": greedy_actor(initial, hidden_sizes)},
                        settings, seeds, episodes, private / folder,
                        {"kind": "baseline", **labels, "rule": A_WAITS_BASELINE, "mask": mask_name}, code)
                    
                    measured(folder, [job_id(folder, "evaluate")], True, None, None, None)

                # controls applied to the cue-visible teams only.
                if arm == "cue-visible":
                    for control in study.controls:
                        folder = control_folder(study, world, control, seed)
                        add(folder,
                            "evaluate", 
                            "evaluate",
                            [job_id(team, "train")], 
                            jobs.evaluate,
                            team_policies,
                            world_settings(study, world, [mask, CONTROLS[control]]), 
                            seeds, 
                            episodes,
                            private / folder,
                            {"kind": "control", **labels, "control": control, "mask": control}, 
                            code)
                        
                        measured(folder, [job_id(folder, "evaluate")], False, None, None, None)
                        
                        add(folder, 
                            "measure_control", 
                            "measure_control",
                            [job_id(team, "measure_evaluation"), job_id(folder, "measure_evaluation")],
                            jobs.measure_control, 
                            public / team, 
                            public / folder, 
                            sender, 
                            seeds)

        
        if sender:
            for seed in study.seeds:
                
                sources = []
                needs = []
                
                for arm in study.arms:
                    
                    before = before_folder(study, world, arm, seed)
                    sources.append((f"before/{arm}", private / before / "records.jsonl.gz"))
                    needs.append(job_id(before, "evaluate"))
                    
                    
                for folder in rule_folders:
                    
                    sources.append((f"baselines/{folder.name}", private / folder / "records.jsonl.gz"))
                    needs.append(job_id(folder, "evaluate"))
                    
                    
                file = probe_list_file(study, world, seed)
                
                add(file.parent, 
                    f"probe_list-seed{seed}",
                    "probe_list", 
                    needs, 
                    jobs.probe_list,
                    sources,
                    world_config, 
                    private / file, 
                    private / probe_sources_file(study, world, seed))


        here = world_folder(study, world)
        arms = {}
        teams = {}
        baselines = []
        controls = {}
        evaluated = []
        world_needs = []

        for name in study.baselines:
            
            if name == A_WAITS_BASELINE:
                
                for arm in study.arms:
                    for seed in study.seeds:
                        folder = a_waits_folder(study, world, arm, seed)
                        baselines.append((name, arm, seed, public / folder))
                        evaluated.append(folder)
                        world_needs.append(job_id(folder, "measure_evaluation"))
                        
            else:
                folder = baseline_folder(study, world, name)
                baselines.append((name, "", "", public / folder))
                evaluated.append(folder)
                world_needs.append(job_id(folder, "measure_evaluation"))

        for arm in study.arms:

            arm_teams = {}
            arm_controls = {}
            needs = []

            for seed in study.seeds:
                team = team_folder(study, world, arm, seed)
                arm_teams[seed] = public / team
                teams[(arm, seed)] = public / team
                evaluated.append(team)
                needs.extend([job_id(team, "train"), job_id(team, "measure_evaluation")])
                if sender:
                    evaluated.append(before_folder(study, world, arm, seed))
                    needs.append(job_id(team, "training_series"))

            if arm == "cue-visible":
                for control in study.controls:
                    arm_controls[control] = {}
                    for seed in study.seeds:
                        folder = control_folder(study, world, control, seed)
                        arm_controls[control][seed] = public / folder
                        controls[(control, seed)] = public / folder
                        evaluated.append(folder)
                        needs.append(job_id(folder, "measure_control"))

            folder = arm_folder(study, world, arm)
            
            add(folder,
                "measure_arm", 
                "measure_arm", 
                needs,
                jobs.measure_arm,
                arm_teams, 
                arm_controls,
                sender, 
                public / folder)
            
            arms[arm] = public / folder
            world_needs.append(job_id(folder, "measure_arm"))

        add(here, "measure_world", "measure_world", world_needs, jobs.measure_world,
            arms, teams, baselines, controls, sender, public / here)
        add(here, "draw_world", "draw_world", [job_id(here, "measure_world")], jobs.draw_world,
            public / here, arms, sender, figure_names(study, "world"), public / here / "figures")

    
        lists[world] = private / here / "handpicked.toml"
        relative = []
        for folder in evaluated:
            relative.append(folder.relative_to(here).as_posix())
        add(here, "handpicked", "handpicked", [job_id(here, "measure_world")], jobs.handpicked,
            lists[world], relative, public / here, private / here, public / baseline_folder(study, world, "always-wait"))

        worlds[world] = (public / here, arms)


    
    here = study_folder(study)
    needs = []
    readme_worlds = {}
    readme_needs = [job_id(here, "measure_study"), job_id(here, "draw_study")]
    for world, (folder, arms) in worlds.items():
        needs.append(job_id(world_folder(study, world), "measure_world"))
        readme_worlds[world] = (folder, arms, lists[world])
        readme_needs.append(job_id(world_folder(study, world), "draw_world"))
        readme_needs.append(job_id(world_folder(study, world), "handpicked"))

    add(here, "measure_study", "measure_study", needs, jobs.measure_study, worlds, sender, public / here)
    add(here, "draw_study", "draw_study", needs, jobs.draw_study,
        worlds, sender, figure_names(study, "study"), public / here / "figures")
    add(here, "write_readmes", "write_readmes", readme_needs, jobs.write_readmes,
        study.folder, public / here, readme_worlds, sender, figure_names(study, "world"), figure_names(study, "study"))

    return result



#joined graph
def launch_jobs(numbers: list[int], smoke: bool, code: dict, full: bool = False) -> list[Job]:

    graph = []
    ids = set()
    
    for number in numbers:
        
        for job in study_jobs(STUDIES[number], smoke, code, full):
            if job.id in ids:
                raise ValueError(f"two jobs are {job.id}")
            
            
            ids.add(job.id)
            graph.append(job)


    senders = []
    for number, study in STUDIES.items():
        if study.kind == "sender":
            senders.append(number)

    if set(senders) <= set(numbers):

        public, _ = roots(smoke, full)
        root = Path(".")
        masters = {}
        needs = []

        for number in senders:
            study = STUDIES[number]
            masters[study.folder] = (public / study_folder(study), list(study.arms))
            needs.append(job_id(study_folder(study), "measure_study"))

        graph.append(Job(job_id(root, "measure_cross_study"), 
                         "measure_cross_study", 
                         tuple(needs),
                         partial(jobs.measure_cross_study, masters, public)))
        
        graph.append(Job(job_id(root, "draw_cross_study"), 
                         "draw_cross_study", 
                         (job_id(root, "measure_cross_study"),),
                         partial(jobs.draw_cross_study,
                                 public / "sender-studies-summary.csv",
                                 public)))

    return graph




def jobs_to_run(graph: list[Job], private: Path, only: list[str] | None, smoke: bool) -> tuple[list[Job], list[str]]:

    kinds = set()
    
    if only is not None:
        for group in only:
            kinds.update(GROUPS[group])

    chosen = set()
    
    for job in graph:
        
        if only is not None:
            if job.kind in kinds:
                chosen.add(job.id)
                
        elif smoke or not marker(private, job.id).exists():
            chosen.add(job.id)



    growing = True
    while growing:
        growing = False
        for job in graph:
            if job.id in chosen:
                continue
            for need in job.needs:
                if need in chosen:
                    chosen.add(job.id)
                    growing = True
                    break

    run = []
    missing = []
    
    for job in graph:
        if job.id not in chosen:
            continue
        
        run.append(job)
        
        for need in job.needs:
            if need not in chosen and need not in missing and not marker(private, need).exists():
                missing.append(need)

    return run, missing


def other_commit_markers(graph: list[Job], run: list[Job], private: Path, commit: str) -> list[Path]:

    chosen = set()
    for job in run:
        chosen.add(job.id)

    relied = set()
    for job in graph:
        if job.id not in chosen:
            relied.add(job.id)
        for need in job.needs:
            if need not in chosen:
                relied.add(need)

    result = []
    
    for id in sorted(relied):
        file = marker(private, id)
        if file.exists() and read_run_json(file)["code"]["commit"] != commit:
            result.append(file)

    return result


