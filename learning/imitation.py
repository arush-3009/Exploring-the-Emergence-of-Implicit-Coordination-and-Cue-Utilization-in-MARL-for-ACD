import numpy as np
import torch

from episodes.runner import EpisodeLog, Policy
from learning.advantages import advantages_and_returns
from learning.experience import defender_decisions
from learning.networks import Actor, Critic
from policies.always_wait import WAIT_ACTION_ID
from policies.inspect_then_restore import InspectThenRestore
from policies.restore_reconnect_only_when_helpful import RestoreReconnectOnlyWhenHelpful
from world.environment import WorldEnvironment

TEACHERS = {"restore-on-warning": RestoreReconnectOnlyWhenHelpful,
            "inspect-then-restore": InspectThenRestore,
            "inspect-then-restore-prob-restore-weakened": InspectThenRestore}


def _check_finite(network: torch.nn.Module, name: str) -> None:
    if not all(torch.isfinite(weights).all() for weights in network.parameters()):
        raise FloatingPointError(f"{name} weights are no longer finite after the imitation fit")
   
    
    
    
def teacher_policies(environment: WorldEnvironment, rule: str) -> dict[str, Policy]:

    if rule not in TEACHERS:
        raise ValueError(f"rule must be one of {list(TEACHERS)}, not {rule!r}")


    teacher = TEACHERS[rule]
    zones = environment.configuration_snapshot()["world"]["zones"]

    policies = {}
    for defender_id in environment.get_defender_ids():
        policies[defender_id] = teacher(len(zones[defender_id]["servers"]))

    return policies


# Join one defender's decisions from the teacher's episodes into one batch.
def teacher_batch(logs: list[EpisodeLog], defender_id: str, gamma: float) -> dict[str, np.ndarray]:

    observations, action_ids, returns = [], [], []

    for log in logs:

        decisions = defender_decisions(log=log, defender_id=defender_id)

        _, episode_returns = advantages_and_returns(shared_rewards=log.shared_rewards,
                                                    decision_intervals=decisions.intervals,
                                                    values=np.zeros(len(decisions.intervals)),
                                                    gamma=gamma,
                                                    gae_lambda=1.0)

        observations.append(decisions.observations)
        action_ids.append(decisions.action_ids)
        returns.append(episode_returns)

    return {"observations": np.concatenate(observations),
            "action_ids": np.concatenate(action_ids),
            "returns": np.concatenate(returns)}






def soft_targets(action_ids: torch.Tensor,
                 action_count: int,
                 action_target_weight: float,
                 wait_target_weight: float,
                 *, restore_target_weight: float | None = None,
                 action_choices=None) -> torch.Tensor:


    if action_count < 2:
        raise ValueError("action_count must be at least 2 to spread probability over other actions")


    weights = torch.full((len(action_ids),), float(action_target_weight))
    weights[action_ids == WAIT_ACTION_ID] = float(wait_target_weight)
    
    if restore_target_weight is not None:
        
        if action_choices is None or len(action_choices) != action_count:
            raise ValueError("Restore targets require the matching action list.")
        
        for action_id, (action, _) in enumerate(action_choices):
            if action == "restore":
                weights[action_ids == action_id] = float(restore_target_weight)


    targets = ((1 - weights) / (action_count - 1)).unsqueeze(1).repeat(1, action_count)
    targets[torch.arange(len(action_ids)), action_ids] = weights

    return targets





def fit_actor(actor: Actor,
              observations: np.ndarray,
              action_ids: np.ndarray,
              settings: dict,
              seed: int,
              *, action_choices=None) -> dict:

    observations = torch.as_tensor(observations, dtype=torch.float32)
    action_ids = torch.as_tensor(action_ids, dtype=torch.int64)

    acting = action_ids != WAIT_ACTION_ID
    if not acting.any():
        raise ValueError("The teacher never chose anything but Wait in these episodes; there is nothing to imitate")

    targets = soft_targets(action_ids, actor.action_count,
                           settings["action_target_weight"], settings["wait_target_weight"],
                           restore_target_weight=settings.get("restore_target_weight"), action_choices=action_choices)

    optimizer = torch.optim.Adam(actor.parameters(), lr=settings["learning_rate"])
    generator = torch.Generator().manual_seed(seed)

    for _ in range(settings["epochs"]):

        order = torch.randperm(len(observations), generator=generator)

        for minibatch in order.split(settings["minibatch_size"]):

            log_probabilities = torch.log_softmax(actor(observations[minibatch]), dim=1)
            loss = -(targets[minibatch] * log_probabilities).sum(dim=1).mean()

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

    _check_finite(actor, "Actor")

    with torch.no_grad():
        log_probabilities = torch.log_softmax(actor(observations), dim=1)
        chosen = log_probabilities.argmax(dim=1)

        return {"loss": -(targets * log_probabilities).sum(dim=1).mean().item(),
                "agreement": (chosen == action_ids).float().mean().item(),
                "action_agreement": (chosen[acting] == action_ids[acting]).float().mean().item(),
                "decisions": len(action_ids),
                "action_decisions": int(acting.sum())}


def fit_critic(critic: Critic,
               observations: np.ndarray,
               returns: np.ndarray,
               settings: dict,
               seed: int) -> dict:

    observations = torch.as_tensor(observations, dtype=torch.float32)
    returns = torch.as_tensor(returns, dtype=torch.float32)

    optimizer = torch.optim.Adam(critic.parameters(), lr=settings["learning_rate"])
    generator = torch.Generator().manual_seed(seed)

    for _ in range(settings["epochs"]):

        order = torch.randperm(len(observations), generator=generator)

        for minibatch in order.split(settings["minibatch_size"]):

            loss = ((critic(observations[minibatch]) - returns[minibatch]) ** 2).mean()

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

    _check_finite(critic, "Critic")

    with torch.no_grad():
        return {"loss": ((critic(observations) - returns) ** 2).mean().item()}
