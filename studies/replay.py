from itertools import islice

import torch

from episodes.record import EpisodeRecord
from episodes.record_io import sha256_of
from episodes.runner import EpisodeLog, EpisodeRunner, evaluation_seeds
from learning.networks import Actor
from policies.always_wait import AlwaysWait
from policies.neural_policy import NeuralPolicy
from policies.random_policy import RandomPolicy
from studies.definitions import RULES
from world.environment import WorldEnvironment
from world.environment_interface import EnvironmentInterface


def rule_policy(rule: str, environment: WorldEnvironment, defender: str, sampling_seed: int):

    policy = RULES[rule]
    
    if policy is AlwaysWait:
        return AlwaysWait()
    
    if policy is RandomPolicy:
        return RandomPolicy(len(environment.action_choices(defender)), sampling_seed)

    servers = environment.configuration_snapshot()["world"]["zones"][defender]["servers"]
    return policy(len(servers))



def build_policies(spec: dict, environment: WorldEnvironment, sampling_seeds: dict) -> dict:

    if set(spec) != set(environment.get_defender_ids()):
        raise ValueError(f"the policies name {sorted(spec)}, the world's defenders are {environment.get_defender_ids()}")


    policies = {}
    for defender in environment.get_defender_ids():
        entry = spec[defender]

        if entry["type"] == "rule":
            policies[defender] = rule_policy(entry["rule"], environment, defender, sampling_seeds[defender])

        elif entry["type"] == "greedy-actor":
            
            if sha256_of(entry["weights"]) != entry["sha256"]:
                raise ValueError(f"{entry['weights']} is not the weights file this evaluation played")
            
            actor = Actor(len(environment.encode_observation(defender)),
                          len(environment.action_choices(defender)),
                          entry["hidden_sizes"])
            
            actor.load_state_dict(torch.load(entry["weights"], weights_only=True)[defender]["actor"])
            policies[defender] = NeuralPolicy(actor, seed=sampling_seeds[defender], mode="greedy")

        else:
            raise ValueError(f"unknown policy type {entry['type']!r}")

    return policies



def play(spec: dict, settings: dict, evaluation_seed: int):

    environment = WorldEnvironment(settings)
    sampling_seeds, world_seed = evaluation_seeds(evaluation_seed, environment.get_defender_ids())
    runner = EpisodeRunner(EnvironmentInterface(environment), build_policies(spec, environment, sampling_seeds))
    environment.set_world_rng(world_seed)

    episode = 0
    while True:
        log = runner.run()
        yield log, EpisodeRecord.from_log(log, settings["world"], episode, evaluation_seed=evaluation_seed)
        episode += 1


def replay_episode(run: dict, evaluation_seed: int, episode: int) -> tuple[EpisodeLog, EpisodeRecord]:

    if evaluation_seed not in run["evaluation_seeds"] or not 0 <= episode < run["episodes_per_seed"]:
        raise ValueError(f"the evaluation did not play episode {episode} of evaluation seed {evaluation_seed}")

    return next(islice(play(run["policies"], run["settings"], evaluation_seed), episode, None))
