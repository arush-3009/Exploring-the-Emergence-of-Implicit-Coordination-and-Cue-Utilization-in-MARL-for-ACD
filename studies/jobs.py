import copy
import hashlib
import json
import platform as platform_module
import random
import shutil
import tomllib
from datetime import datetime
from itertools import islice
from pathlib import Path

import numpy
import torch

from episodes.record import EpisodeRecord, action_labels
from episodes.record_io import (
    read_records,
    read_run_json,
    sha256_of,
    write_records,
    write_run_json,
)
from episodes.runner import EpisodeRunner
from figures import study_figures, world_figures
from figures.readme import study_readme, world_readme
from learning.imitation import fit_actor, fit_critic, teacher_batch, teacher_policies
from learning.imitation_config import validate_imitation_config
from learning.ippo_trainer import IPPOTrainer
from learning.networks import Actor, Critic
from measurements.arm import (
    arm_columns,
    arm_learning_curve,
    arm_summary,
    arm_training_behaviour,
    learning_curve_columns,
    training_behaviour_columns,
)
from measurements.controls import control_measurements, paired_columns
from measurements.episode import episode_columns, measure_episode
from measurements.glossary import write_measurements_csv
from measurements.interruptions import INTERRUPTION_COLUMNS, interruptions_of
from measurements.opportunities import OPPORTUNITY_COLUMNS, opportunities_of
from measurements.probe import (
    SOURCE_COLUMNS,
    build_probe_list,
    probe_list_columns,
    probe_measurements,
)
from measurements.study import (
    master_table,
    sender_studies_summary,
    sender_summary_columns,
)
from measurements.tables import append_csv, read_csv, write_csv
from measurements.team import team_columns, team_measurements
from measurements.training_series import training_behaviour, training_columns
from measurements.world import world_columns, world_table
from observations.schema import observation_feature_names
from studies.definitions import apply_dotted_overrides
from studies.paths import folder_label
from studies.replay import play, replay_episode
from tools.timeline import stacked_html, timeline_html
from world.environment import WorldEnvironment
from world.environment_interface import EnvironmentInterface

PPO_STATISTICS = ("actor_loss", "critic_loss", "clip_fraction", "entropy")

SAMPLE_EVERY = 100


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def platform() -> dict:
    return {"python": platform_module.python_version(),
            "torch": torch.__version__,
            "numpy": numpy.__version__,
            "system": platform_module.platform()}


def fresh(*paths: Path) -> None:
    for path in paths:
        path.unlink(missing_ok=True)


def save_weights(path: Path, weights: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    torch.save(weights, temporary)
    temporary.replace(path)



def weights_hash(networks: dict) -> str:

    digest = hashlib.sha256()
    for network in ("actor", "critic"):
        for key in sorted(networks[network]):
            tensor = networks[network][key]
            digest.update(f"{network}.{key}{tuple(tensor.shape)}".encode())
            digest.update(tensor.numpy().tobytes())

    return digest.hexdigest()



def same_weights(first: dict, second: dict) -> bool:

    for network in ("actor", "critic"):
        if first[network].keys() != second[network].keys():
            return False
        for key in first[network]:
            if not torch.equal(first[network][key], second[network][key]):
                return False

    return True


def weights_entry(path: Path, weights: dict) -> dict:

    entry = {"file": path.as_posix(), "sha256": sha256_of(path)}
    for defender, networks in weights.items():
        entry[defender] = weights_hash(networks)

    return entry



def schema(settings: dict) -> dict:

    world = settings["world"]
    features = {}
    choices = {}
    
    for defender, zone in world["zones"].items():
        features[defender] = list(observation_feature_names(len(zone["servers"])))
        choices[defender] = action_labels(world, defender)

    return {"observation_features": features, 
            "action_choices": choices}


#play teacher to fit actor and critic.
def warm_start(settings: dict, 
               training: dict, 
               imitation: dict, 
               seed: int, 
               fit: tuple,
               defender_overrides: dict,
               out: Path, 
               code: dict) -> None:

    weights_file = out / "weights/warm_start.pt"
    info_file = out / "warm_start.json"
    fresh(weights_file, info_file)
    started = now()

    environment = WorldEnvironment(settings)
    hidden_sizes = training["networks"]["hidden_sizes"]

    # every defender's seeds in turn, then the world seed, so the teacher's episodes do not depend on who is fitted.
    draws = random.Random(seed)
    seeds = {}
    networks = {}
    for defender in environment.get_defender_ids():
        
        seeds[defender] = {"weights": draws.randrange(2**31),
                           "sampling": draws.randrange(2**31),
                           "actor_fit": draws.randrange(2**31),
                           "critic_fit": draws.randrange(2**31)}
        
        if defender in fit:
            observation_size = len(environment.encode_observation(defender))
            torch.manual_seed(seeds[defender]["weights"])
            networks[defender] = (Actor(observation_size, len(environment.action_choices(defender)), hidden_sizes),
                                  Critic(observation_size, hidden_sizes))
            
    world_seed = draws.randrange(2**31)
    environment.set_world_rng(world_seed)

    runner = EpisodeRunner(EnvironmentInterface(environment),
                           teacher_policies(environment, imitation["teacher"]["rule"]))
    
    logs = []
    total = 0.0
    
    for _ in range(imitation["teacher"]["episodes"]):
        log = runner.run()
        logs.append(log)
        total += log.total_episode_reward


    weights = {}
    statistics = {}
    imitation_by_defender = {}
    
    for defender in fit:
        
        actor, critic = networks[defender]

        defender_imitation = copy.deepcopy(imitation)
        if defender in defender_overrides:
            apply_dotted_overrides(defender_imitation, defender_overrides[defender])
        validate_imitation_config(defender_imitation)
        imitation_by_defender[defender] = defender_imitation
        
        batch = teacher_batch(logs, defender, training["advantages"]["gamma"])
        actor_statistics = fit_actor(actor, 
                                     batch["observations"], 
                                     batch["action_ids"],
                                     defender_imitation["actor_fit"],
                                     seeds[defender]["actor_fit"], 
                                     action_choices=environment.action_choices(defender))
        
        critic_statistics = fit_critic(critic,
                                       batch["observations"], 
                                       batch["returns"], 
                                       defender_imitation["critic_fit"],
                                       seeds[defender]["critic_fit"])
        
        weights[defender] = {"actor": actor.state_dict(),
                             "critic": critic.state_dict()}
        
        statistics[defender] = {"actor": actor_statistics, 
                                "critic": critic_statistics}
        
        print(f"{defender} fitted on {actor_statistics['decisions']} decisions, agreement {actor_statistics['agreement']:.4f}", 
              flush=True)


    save_weights(weights_file, weights)
    write_run_json(info_file, 
                   {"seed": seed,
                    "defender_seeds": seeds,
                    "world_seed": world_seed,
                    "fitted": list(fit),
                    "teacher_mean_reward": total / len(logs),
                    "fit": statistics,
                    "imitation": imitation,
                    "imitation_by_defender": imitation_by_defender,
                    "networks": training["networks"],
                    "gamma": training["advantages"]["gamma"],
                    "weights_sha256": sha256_of(weights_file),
                    "code": code,
                    "platform": platform(),
                    "started": started,
                    "finished": now()})


def initial_weights(starts: dict, 
                    settings: dict,
                    training: dict,
                    seed: int, 
                    public: Path,
                    private: Path,
                    code: dict) -> None:

    weights_file = public / "weights/initial.pt"
    info_file = private / "initial_weights.json"
    fresh(weights_file, info_file)
    started = now()

    environment = WorldEnvironment(settings)
    hidden_sizes = training["networks"]["hidden_sizes"]

    
    draws = random.Random(seed)
    trainer_seeds = {}
    for defender in environment.get_defender_ids():
        trainer_seeds[defender] = {"weights": draws.randrange(2**31),
                                   "sampling": draws.randrange(2**31),
                                   "shuffling": draws.randrange(2**31)}

    weights = {}
    sources = {}
    warm = None
    for defender in environment.get_defender_ids():
        start = starts[defender]

        if start["start"] == "random":
            observation_size = len(environment.encode_observation(defender))
            torch.manual_seed(trainer_seeds[defender]["weights"])
            actor = Actor(observation_size, len(environment.action_choices(defender)), hidden_sizes)
            critic = Critic(observation_size, hidden_sizes)
            weights[defender] = {"actor": actor.state_dict(), "critic": critic.state_dict()}
            sources[defender] = {"start": "random", "weights_seed": trainer_seeds[defender]["weights"]}


        elif start["start"] in ("warm-start", "study-1-team"):
            
            weights[defender] = torch.load(start["weights"], weights_only=True)[defender]
            
            sources[defender] = {"start": start["start"],
                                 "source": start["weights"].as_posix(),
                                 "source_sha256": sha256_of(start["weights"])}
            
            if start["start"] == "warm-start":
                warm = read_run_json(start["info"])

        else:
            raise ValueError(f"unknown start {start['start']!r}")


        sources[defender]["weights_hash"] = weights_hash(weights[defender])

    save_weights(weights_file, weights)
    write_run_json(info_file, {"seed": seed,
                               "defenders": sources,
                               "warm_start": warm,
                               "file": weights_file.as_posix(),
                               "sha256": sha256_of(weights_file),
                               "code": code,
                               "started": started,
                               "finished": now()})


def train(settings: dict,
          training: dict, 
          seed: int, 
          world_seed: int | None, 
          sender: bool, 
          initial: Path,
          fixed_source: Path | None, 
          probe_list: Path | None, 
          public: Path,
          private: Path, 
          labels: dict,
          code: dict) -> None:


    final_file = public / "weights/final.pt"
    curve_file = public / "learning_curve.csv"
    run_file = public / "run.json"
    folder = private / "training"
    episodes_file = folder / "training_episodes.csv"
    interruptions_file = folder / "training_interruptions.csv"
    opportunities_file = folder / "training_opportunities.csv"
    sample_file = folder / "records-sample.jsonl.gz"
    fresh(final_file, curve_file, run_file, episodes_file, interruptions_file, opportunities_file, sample_file)
    started = now()


    probe = None
    if probe_list is not None:
        probe = {"file": probe_list.as_posix(), "sha256": sha256_of(probe_list)}

    world = settings["world"]
    environment = WorldEnvironment(settings)
    start = torch.load(initial, weights_only=True)
    trainer = IPPOTrainer(environment, training, seed, initial_weights=start, initial_weights_source=initial.as_posix())


    if world_seed is not None:
        environment.set_world_rng(world_seed)
    used_world_seed = environment.world_seed

    learning = []
    for defender in environment.get_defender_ids():
        if defender not in trainer.fixed_defenders:
            learning.append(defender)

    curve_columns = ["iteration", "mean_reward"]
    for defender in learning:
        for name in PPO_STATISTICS:
            curve_columns.append(f"{defender}_{name}")

    columns = episode_columns(world)
    curve = []
    sample = []

    for iteration in range(1, training["training"]["iterations"] + 1):

        logs, statistics = trainer.run_iteration()

        episode_rows = []
        interruption_rows = []
        opportunity_rows = []
        total = 0.0
        
        for episode, log in enumerate(logs):
            
            record = EpisodeRecord.from_log(log, world, episode, iteration=iteration)
            
            episode_rows.append(measure_episode(record, world, sender))
            
            if sender:
                interruption_rows.extend(interruptions_of(record, world))
                opportunity_rows.extend(opportunities_of(record, world))
                
            if episode == 0 and (iteration == 1 or iteration % SAMPLE_EVERY == 0):
                sample.append(record)
                
            total += log.total_episode_reward

        append_csv(episodes_file, episode_rows, columns)
        
        if sender:
            append_csv(interruptions_file, interruption_rows, INTERRUPTION_COLUMNS)
            append_csv(opportunities_file, opportunity_rows, OPPORTUNITY_COLUMNS)

        row = {"iteration": iteration, "mean_reward": total / len(logs)}
        for defender in learning:
            for name in PPO_STATISTICS:
                row[f"{defender}_{name}"] = statistics[defender][name]
                
        curve.append(row)

        if iteration == 1 or iteration % SAMPLE_EVERY == 0:
            print(f"iteration {iteration}, mean reward {row['mean_reward']:.3f}", flush=True)

    write_records(sample_file, sample)
    write_csv(curve_file, curve, curve_columns)

    final = {}
    for defender, learner in trainer.learners.items():
        final[defender] = {"actor": learner.actor.state_dict(), "critic": learner.critic.state_dict()}
        
    save_weights(final_file, final)

    fixed = {}
    
    for defender in trainer.fixed_defenders:
        
        source = torch.load(fixed_source, weights_only=True)[defender]
        
        if not same_weights(start[defender], source) or not same_weights(final[defender], source):
            raise AssertionError(f"the fixed {defender}'s weights differ from those of {fixed_source}")
        
        
        fixed[defender] = {"source": fixed_source.as_posix(),
                           "source_sha256": sha256_of(fixed_source),
                           "weights_hash": weights_hash(source),
                           "equal_before_training": True,
                           "equal_after_training": True}


    write_run_json(run_file, {"kind": "team",
                              **labels,
                              "settings": settings,
                              "training": trainer.describe(),
                              "world_seed": used_world_seed,
                              "initial_weights": read_run_json(private / "initial_weights.json"),
                              "weights": {"initial": weights_entry(initial, start), 
                                          "final": weights_entry(final_file, final)},
                              "fixed_defenders": fixed,
                              "probe_list": probe,
                              "schema": schema(settings),
                              "code": code,
                              "platform": platform(),
                              "started": started,
                              "finished": now()})


def evaluate(policies: dict, 
             settings: dict,
             seeds: tuple, 
             episodes: int,
             out: Path, 
             labels: dict,
             code: dict) -> None:


    records_file = out / "records.jsonl.gz"
    run_file = out / "run.json"
    fresh(records_file, run_file)
    started = now()

    spec = {}
    for defender, entry in policies.items():
        entry = dict(entry)
        
        if entry["type"] == "greedy-actor":
            entry["sha256"] = sha256_of(entry["weights"])
            
        spec[defender] = entry

    first = {}

    def played():
        for evaluation_seed in seeds:
            for _, record in islice(play(spec, settings, evaluation_seed), episodes):
                if record.episode == 0:
                    first[evaluation_seed] = record
                yield record

    write_records(records_file, played())
    write_run_json(run_file, {**labels,
                              "policies": spec,
                              "evaluation_seeds": list(seeds),
                              "episodes_per_seed": episodes,
                              "settings": settings,
                              "schema": schema(settings),
                              "code": code,
                              "platform": platform(),
                              "started": started,
                              "finished": now()})

    
    run = read_run_json(run_file)
    
    for evaluation_seed in seeds:
        
        _, replayed = replay_episode(run, evaluation_seed, 0)
        written = json.loads(json.dumps(first[evaluation_seed].to_dict()))
        again = json.loads(json.dumps(replayed.to_dict()))
        
        for field in written:
            if written[field] != again[field]:
                raise AssertionError(f"episode 0 of evaluation seed {evaluation_seed} replays differently in {field}")


def probe_list(sources: list, world: dict, out: Path, sources_out: Path) -> None:


    fresh(out, sources_out)

    readers = []
    for label, path in sources:
        readers.append((label, read_records(path)))

    list_rows, source_rows = build_probe_list(readers, world)
    write_csv(out, list_rows, probe_list_columns(world))
    write_csv(sources_out, source_rows, SOURCE_COLUMNS)


def probe(weights: Path, settings: dict, hidden_sizes: list, probe_list: Path, out: Path) -> None:

    fresh(out)

    environment = WorldEnvironment(settings)
    actor = Actor(len(environment.encode_observation("A")), len(environment.action_choices("A")), hidden_sizes)
    actor.load_state_dict(torch.load(weights, weights_only=True)["A"]["actor"])
    labels = action_labels(settings["world"], "A")

    rows = []
    for entry in read_csv(probe_list):
        
        observation = json.loads(entry["observation"])
    
        with torch.no_grad():
            scores = actor(torch.tensor(environment.encode("A", observation), dtype=torch.float32))
            
        probabilities = torch.softmax(scores, dim=0).tolist()

        row = {"probe": entry["probe"]}
        for label, probability in zip(labels, probabilities, strict=True):
            row[label] = probability
            
        row["greedy"] = labels[int(scores.argmax())]
        
        rows.append(row)

    write_csv(out, rows, ["probe", *labels, "greedy"])



def measure_evaluation(records: Path, 
                       world: dict, 
                       sender: bool,
                       seeds: tuple, 
                       out: Path,
                       summarise: bool,
                       probe_list: Path | None, 
                       probe_answers: Path | None,
                       before: Path | None) -> None:

    episodes_file = out / "episodes.csv"
    interruptions_file = out / "interruptions.csv"
    opportunities_file = out / "opportunities.csv"
    measurements_file = out / "team_measurements.csv"
    
    fresh(episodes_file, interruptions_file, opportunities_file)
    
    if summarise:
        fresh(measurements_file)

    episode_rows = []
    interruption_rows = []
    opportunity_rows = []
    
    for record in read_records(records):
        
        episode_rows.append(measure_episode(record, world, sender))
        
        if sender:
            interruption_rows.extend(interruptions_of(record, world))
            opportunity_rows.extend(opportunities_of(record, world))


    write_csv(episodes_file, episode_rows, episode_columns(world))
    
    if sender:
        write_csv(interruptions_file, interruption_rows, INTERRUPTION_COLUMNS)
        write_csv(opportunities_file, opportunity_rows, OPPORTUNITY_COLUMNS)

    if not summarise:
        return

    probe_rows = None
    if probe_list is not None:
        assert probe_answers is not None, "a probe list needs the answers file that goes with it"
        probe_rows = probe_measurements(read_csv(probe_list), read_csv(probe_answers), world)

    before_rows = None
    if before is not None:
        before_rows = read_csv(before / "team_measurements.csv")

    seed_names = []
    for seed in seeds:
        seed_names.append(str(seed))

    rows = team_measurements(read_csv(episodes_file), probe_rows, sender, before_rows)
    write_csv(measurements_file, rows, team_columns(seed_names))


def measure_control(team: Path, control: Path, sender: bool, seeds: tuple) -> None:

    paired_file = control / "paired.csv"
    measurements_file = control / "team_measurements.csv"
    fresh(paired_file, measurements_file)

    control_rows = read_csv(control / "episodes.csv")
    paired, ctrl = control_measurements(read_csv(team / "episodes.csv"), control_rows, sender)
    write_csv(paired_file, paired, paired_columns(sender))

    seed_names = []
    for seed in seeds:
        seed_names.append(str(seed))

    rows = team_measurements(control_rows, None, sender)
    rows.extend(ctrl)
    write_csv(measurements_file, rows, team_columns(seed_names))


def training_series(training_episodes: Path, out: Path) -> None:
    fresh(out)
    write_csv(out, training_behaviour(read_csv(training_episodes)), training_columns())


def measure_arm(teams: dict, controls: dict, sender: bool, out: Path) -> None:

    summary_file = out / "arm_summary.csv"
    curve_file = out / "learning_curve.csv"
    behaviour_file = out / "training_behaviour.csv"
    
    fresh(summary_file, curve_file, behaviour_file)

    seeds = list(teams)
    team_rows = {}
    curves = {}
    series = {}
    
    for seed, folder in teams.items():
        
        team_rows[seed] = read_csv(folder / "team_measurements.csv")
        curves[seed] = read_csv(folder / "learning_curve.csv")
        
        if sender:
            series[seed] = read_csv(folder / "training_behaviour.csv")

    control_rows = {}
    
    for control, folders in controls.items():
        
        control_rows[control] = {}
        
        for seed, folder in folders.items():
            control_rows[control][seed] = read_csv(folder / "team_measurements.csv")


    write_csv(summary_file, arm_summary(team_rows, control_rows, sender), arm_columns(seeds, sender))
    write_csv(curve_file, arm_learning_curve(curves), learning_curve_columns(seeds))

    if sender:
        write_csv(behaviour_file, arm_training_behaviour(series), training_behaviour_columns())


def measure_world(arms: dict, teams: dict, baselines: list, controls: dict, sender: bool, out: Path) -> None:

    table_file = out / "world_table.csv"
    fresh(table_file)

    summaries = {}
    for arm, folder in arms.items():
        summaries[arm] = read_csv(folder / "arm_summary.csv")

    team_rows = {}
    for key, folder in teams.items():
        team_rows[key] = read_csv(folder / "team_measurements.csv")

    baseline_rows = []
    for name, arm, seed, folder in baselines:
        baseline_rows.append((name, arm, seed, read_csv(folder / "team_measurements.csv")))

    control_rows = {}
    
    control_names = []
    
    for (control, seed), folder in controls.items():
        
        control_rows[(control, seed)] = read_csv(folder / "team_measurements.csv")
        
        if control not in control_names:
            control_names.append(control)


    rows = world_table(summaries, team_rows, baseline_rows, control_rows, sender)
    write_csv(table_file, rows, world_columns(control_names, sender))


def read_worlds(worlds: dict) -> dict:

    result = {}
    for world, (folder, arms) in worlds.items():
        summaries = {}
        for arm, arm_folder in arms.items():
            summaries[arm] = read_csv(arm_folder / "arm_summary.csv")
        result[world] = (read_csv(folder / "world_table.csv"), summaries)

    return result


def measure_study(worlds: dict, sender: bool, out: Path) -> None:

    master_file = out / "master_table.csv"
    measurements_file = out / "measurements.csv"
    fresh(master_file, measurements_file)

    inputs = {}
    for world, (table, summaries) in read_worlds(worlds).items():
        inputs[world] = (summaries, table)

    rows = master_table(inputs, sender)
    write_csv(master_file, rows, list(rows[0]))
    write_measurements_csv(measurements_file, sender)


def measure_cross_study(masters: dict, out: Path) -> None:

    summary_file = out / "sender-studies-summary.csv"
    fresh(summary_file)

    inputs = {}
    for study, (folder, arms) in masters.items():
        inputs[study] = (read_csv(folder / "master_table.csv"), arms)

    write_csv(summary_file, sender_studies_summary(inputs), sender_summary_columns())


def figure_files(out: Path, names: tuple, extensions: tuple) -> list[Path]:

    files = []
    for name in names:
        for extension in extensions:
            files.append(out / f"{name}{extension}")

    return files


def draw_world(world: Path, arms: dict, sender: bool, names: tuple, out: Path) -> None:

    fresh(*figure_files(out, names, (".png", ".svg", ".csv")))

    summaries = {}
    curves = {}
    behaviours = {}
    for arm, folder in arms.items():
        summaries[arm] = read_csv(folder / "arm_summary.csv")
        curves[arm] = read_csv(folder / "learning_curve.csv")
        if sender:
            behaviours[arm] = read_csv(folder / "training_behaviour.csv")

    world_figures.draw_world(read_csv(world / "world_table.csv"), summaries, curves, behaviours, sender, out)


def draw_study(worlds: dict, sender: bool, names: tuple, out: Path) -> None:
    fresh(*figure_files(out, names, (".png", ".svg", ".csv")))
    study_figures.draw_study(read_worlds(worlds), sender, out)


def draw_cross_study(summary: Path, out: Path) -> None:
    fresh(*figure_files(out, ("sender-studies-summary",), (".png", ".svg")))
    study_figures.draw_cross_study(read_csv(summary), out)



def handpicked_entries(list_file: Path) -> list[dict]:

    if not list_file.exists():
        return []

    with list_file.open("rb") as file:
        entries = tomllib.load(file)["timeline"]

    pages = []
    
    for entry in entries:
        if set(entry) != {"evaluation_seed", "episode", "folders", "reason"} or not entry["folders"]:
            raise ValueError(f"{list_file}: an entry holds evaluation_seed, episode, folders and reason, not {entry}")
        if world_page(entry) in pages:
            raise ValueError(f"{list_file}: two entries show the same episode in the same folders: {entry}")
        pages.append(world_page(entry))

    return entries


def episode_name(evaluation_seed: int, episode: int) -> str:
    return f"episode-{evaluation_seed}-{episode:03d}"


def world_page(entry: dict) -> str:

    labels = []
    for folder in entry["folders"]:
        labels.append(folder_label(folder))

    return f"{episode_name(entry['evaluation_seed'], entry['episode'])}-{'__'.join(labels)}.html"


def episode_row(path: Path, evaluation_seed: int, episode: int) -> dict:

    for row in read_csv(path):
        if row["evaluation_seed"] == str(evaluation_seed) and row["episode"] == str(episode):
            return row

    raise ValueError(f"{path} has no episode {episode} of evaluation seed {evaluation_seed}")


def handpicked(list_file: Path, folders: list[str], public: Path, private: Path, reference: Path) -> None:

    entries = handpicked_entries(list_file)
    for entry in entries:
        for folder in entry["folders"]:
            if folder not in folders:
                raise ValueError(f"{list_file}: {folder} is not an evaluation folder of this world")

    for folder in [*folders, "."]:
        for name in ("traces", "timelines"):
            if (public / folder / name).exists():
                shutil.rmtree(public / folder / name)

    shown = {}
    for entry in entries:

        seed = entry["evaluation_seed"]
        episode = entry["episode"]
        always_wait = float(episode_row(reference / "episodes.csv", seed, episode)["reward"])
        stacked = []

        for folder in entry["folders"]:

            key = (folder, seed, episode)
            if key not in shown:
                run = read_run_json(private / folder / "run.json")
                _, record = replay_episode(run, seed, episode)

                written = None
                for candidate in read_records(private / folder / "records.jsonl.gz"):
                    if candidate.evaluation_seed == seed and candidate.episode == episode:
                        written = json.loads(json.dumps(candidate.to_dict()))
                        break
                again = json.loads(json.dumps(record.to_dict()))
                for field in written:
                    if written[field] != again[field]:
                        raise AssertionError(f"episode {episode} of evaluation seed {seed} in {folder} replays differently in {field}")

                metrics = episode_row(public / folder / "episodes.csv", seed, episode)
                shown[key] = (record, run, metrics, always_wait, [])

            shown[key][4].append(entry["reason"])
            stacked.append(shown[key][:4])

        page = public / "timelines" / world_page(entry)
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(stacked_html(stacked, entry["reason"]))

    for (folder, seed, episode), (record, run, metrics, always_wait, reasons) in shown.items():
        name = episode_name(seed, episode)
        write_run_json(public / folder / "traces" / f"{name}.json", record.to_dict())
        page = public / folder / "timelines" / f"{name}.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(timeline_html(record, run, metrics, " ".join(reasons), always_wait))


def write_readmes(study: str, 
                  folder: Path,
                  worlds: dict,
                  sender: bool,
                  world_names: tuple,
                  study_names: tuple) -> None:

    files = [folder / "README.md"]
    for world_folder, _, _ in worlds.values():
        files.append(world_folder / "README.md")
    fresh(*files)

    for world, (world_folder, arms, list_file) in worlds.items():

        summaries = {}
        for arm, arm_folder in arms.items():
            summaries[arm] = read_csv(arm_folder / "arm_summary.csv")

        timelines = []
        for entry in handpicked_entries(list_file):
            timelines.append((world_page(entry), entry["reason"]))

        text = world_readme(study, world, sender, read_csv(world_folder / "world_table.csv"), summaries,
                            list(world_names), timelines)
        (world_folder / "README.md").write_text(text)

    text = study_readme(study, 
                        sender,
                        read_csv(folder / "master_table.csv"), 
                        list(study_names), 
                        list(worlds))
    
    (folder / "README.md").write_text(text)
