import random

import numpy as np
import torch

from episodes.runner import EpisodeLog, EpisodeRunner
from learning.advantages import advantages_and_returns
from learning.experience import defender_decisions
from learning.networks import Actor, Critic
from learning.ppo import PPOLearner
from policies.neural_policy import NeuralPolicy
from world.environment import WorldEnvironment
from world.environment_interface import EnvironmentInterface


def get_defender_decisions_batch(logs: list[EpisodeLog],
                                 defender_id: str,
                                 critic: Critic,
                                 gamma: float,
                                 gae_lambda: float) -> dict[str, np.ndarray]:
    

    observations, action_ids, advantages, returns = [], [], [], []

    for log in logs:

        decisions = defender_decisions(log=log, defender_id=defender_id)

        with torch.no_grad():
            values = critic(torch.as_tensor(decisions.observations)).numpy()

        episode_advantages, episode_returns = advantages_and_returns(shared_rewards=log.shared_rewards,
                                                                     decision_intervals=decisions.intervals,
                                                                     values=values,
                                                                     gamma=gamma,
                                                                     gae_lambda=gae_lambda)

        observations.append(decisions.observations)
        action_ids.append(decisions.action_ids)
        advantages.append(episode_advantages)
        returns.append(episode_returns)

    return {"observations": np.concatenate(observations),
            "action_ids": np.concatenate(action_ids),
            "advantages": np.concatenate(advantages),
            "returns": np.concatenate(returns)}


class IPPOTrainer:

    def __init__(self,
                 environment: WorldEnvironment,
                 config: dict,
                 seed: int,
                 initial_weights: dict | None = None,
                 initial_weights_source: str | None = None) -> None:

        if (initial_weights is None) != (initial_weights_source is None):
            raise ValueError("initial_weights and initial_weights_source must be given together")
        if initial_weights is not None and set(initial_weights) != set(environment.get_defender_ids()):
            raise ValueError("initial_weights must hold exactly one entry per defender")

        self.config = config
        self.seed = seed
        self.initial_weights_source = initial_weights_source
        self.fixed_defenders = dict(config.get("fixed_defenders", {}))
        if set(self.fixed_defenders) - set(environment.get_defender_ids()):
            raise ValueError("fixed_defenders contains an unknown defender")
        if self.fixed_defenders and initial_weights is None:
            raise ValueError("Fixed defenders require saved initial weights")
        if len(self.fixed_defenders) == len(environment.get_defender_ids()):
            raise ValueError("At least one defender must learn")
        self.iterations_done = 0

        seed_draws = random.Random(seed)
        self.defender_seeds = {}
        self.learners: dict[str, PPOLearner] = {}
        self.policies = {}

        hidden_sizes = config["networks"]["hidden_sizes"]

        for defender_id in environment.get_defender_ids():

            seeds = {"weights": seed_draws.randrange(2**31),
                     "sampling": seed_draws.randrange(2**31),
                     "shuffling": seed_draws.randrange(2**31)}
            
            self.defender_seeds[defender_id] = seeds

            observation_size = len(environment.encode_observation(defender_id))
            action_count = len(environment.action_choices(defender_id))

            # seed PyTorch shared generator just before creating the neural nets for each defender.
            torch.manual_seed(seeds["weights"])
            actor = Actor(observation_size, action_count, hidden_sizes)
            critic = Critic(observation_size, hidden_sizes)

            if initial_weights is not None:
                try:
                    actor.load_state_dict(initial_weights[defender_id]["actor"])
                    critic.load_state_dict(initial_weights[defender_id]["critic"])
                except (KeyError, RuntimeError) as error:
                    raise ValueError(f"initial weights for {defender_id} do not fit the configured networks "
                                     f"({initial_weights_source}): {error}") from error

            self.learners[defender_id] = PPOLearner(actor, critic, settings=config["ppo"], seed=seeds["shuffling"])
            mode = self.fixed_defenders.get(defender_id, "sample")
            self.policies[defender_id] = NeuralPolicy(actor, seed=seeds["sampling"], mode=mode)
            if defender_id in self.fixed_defenders:
                actor.requires_grad_(False)
                critic.requires_grad_(False)

        # world seed is drawn after every defender's seeds. Every training episode's script is drawn from it.
        environment.set_world_rng(seed_draws.randrange(2**31))

        self.runner = EpisodeRunner(EnvironmentInterface(environment), self.policies)


    def run_iteration(self) -> tuple[list[EpisodeLog], dict[str, dict]]:

        #collect experience for number of episodes given in the configuration.
        logs = []
        for _ in range(self.config["training"]["episodes_per_iteration"]):
            episode_log = self.runner.run()
            logs.append(episode_log)


        iteration_stats = {}
        for defender_id, learner in self.learners.items():
            if defender_id in self.fixed_defenders:
                continue
            
            batch = get_defender_decisions_batch(logs=logs,
                                                 defender_id=defender_id,
                                                 critic=learner.critic,
                                                 gamma=self.config["advantages"]["gamma"],
                                                 gae_lambda=self.config["advantages"]["gae_lambda"])
            
            iteration_stats[defender_id] = learner.update(observations=batch["observations"],
                                                           action_ids=batch["action_ids"],
                                                           advantages=batch["advantages"],
                                                           returns=batch["returns"])

        self.iterations_done += 1

        #raise error if weights diverge.
        for defender_id, learner in self.learners.items():
            for network in (learner.actor, learner.critic):
                if not all(torch.isfinite(weights).all() for weights in network.parameters()):
                    raise FloatingPointError(
                        f"{defender_id}'s {type(network).__name__} weights are no longer finite after iteration {self.iterations_done}; training diverged."
                    )


        return logs, iteration_stats


    def describe(self) -> dict:

        return {"type": "IPPOTrainer",
                "seed": self.seed,
                "defender_seeds": self.defender_seeds,
                "initial_weights": self.initial_weights_source,
                "fixed_defenders": self.fixed_defenders,
                "settings": self.config}
