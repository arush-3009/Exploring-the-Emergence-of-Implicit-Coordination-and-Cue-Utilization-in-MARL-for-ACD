import numpy as np
import torch
from torch.distributions import Categorical

from learning.networks import Actor, Critic


class PPOLearner:

    def __init__(self, actor: Actor, critic: Critic, settings: dict, seed: int) -> None:

        self.actor = actor
        self.critic = critic
        self.settings = settings

        self.actor_optimizer = torch.optim.Adam(actor.parameters(), lr=settings["actor_learning_rate"])
        self.critic_optimizer = torch.optim.Adam(critic.parameters(), lr=settings["critic_learning_rate"])

        self._generator = torch.Generator().manual_seed(seed)


    def update(self,
               observations: np.ndarray, #all these parameters are one vector each containing decisions across multiple episodes.
               action_ids: np.ndarray,
               advantages: np.ndarray,
               returns: np.ndarray) -> dict:

        observations = torch.as_tensor(observations, dtype=torch.float32)
        action_ids = torch.as_tensor(action_ids, dtype=torch.int64)
        returns = torch.as_tensor(returns, dtype=torch.float32)

    
        advantages = torch.as_tensor(advantages, dtype=torch.float32)
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

    
        with torch.no_grad():
            old_log_probs = Categorical(logits=self.actor(observations)).log_prob(action_ids)

        clip = self.settings["clip_epsilon"]
        entropy_coefficient = self.settings["entropy_coefficient"]
        totals = {"actor_loss": 0.0, "critic_loss": 0.0, "clip_fraction": 0.0, "entropy": 0.0}
        steps = 0

        for _ in range(self.settings["epochs"]):
            
            order = torch.randperm(len(observations), generator=self._generator)

            minibatches = order.split(self.settings["minibatch_size"])
            
            for minibatch in minibatches:
                
                policy = Categorical(logits=self.actor(observations[minibatch]))
                
                ratio = torch.exp(policy.log_prob(action_ids[minibatch]) - old_log_probs[minibatch])
                
                unclipped = ratio * advantages[minibatch]
                clipped = torch.clamp(input=ratio, 
                                      min = (1 - clip) , 
                                      max = (1 + clip) ) * advantages[minibatch]
                per_decision_objective = torch.min(unclipped, clipped)
                
                
                entropy = policy.entropy().mean()
                
                #actor update
                actor_loss = -per_decision_objective.mean() - entropy_coefficient * entropy
                
                self.actor_optimizer.zero_grad()
                actor_loss.backward()
                self.actor_optimizer.step()


                #critic update
                critic_loss = ((self.critic(observations[minibatch]) - returns[minibatch]) ** 2).mean()

                self.critic_optimizer.zero_grad()
                critic_loss.backward()
                self.critic_optimizer.step()

                totals["actor_loss"] += actor_loss.item()
                totals["critic_loss"] += critic_loss.item()
                totals["clip_fraction"] += ((ratio - 1).abs() > clip).float().mean().item()
                totals["entropy"] += entropy.item()
                
                steps += 1


        ret = {}
        for name, total in totals.items():
            ret[name] = total / steps
            
        return ret
