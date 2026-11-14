import numpy as np
import torch

from learning.networks import Actor

MODES = ("sample", "greedy")


class NeuralPolicy:
   
    def __init__(self, actor: Actor, seed: int, mode: str) -> None:
        
        if mode not in MODES:
            raise ValueError(f"mode must be one of {MODES}")
        
        self.actor = actor
        self.mode = mode
        self._seed = seed
        self._generator = torch.Generator().manual_seed(seed)


    def __call__(self, observation: np.ndarray) -> int:
        
        with torch.no_grad():
            scores = self.actor(torch.tensor(observation, dtype=torch.float32))
            
        if self.mode == "greedy":
            return int(scores.argmax())
        
        probabilities = torch.softmax(scores, dim=0)
        return int(torch.multinomial(probabilities, 1, generator=self._generator))


    def describe(self) -> dict:

        return {
            "type": "NeuralPolicy",
            "mode": self.mode,
            "seed": self._seed,
            "observation_size": self.actor.observation_size,
            "action_count": self.actor.action_count,
            "hidden_sizes": list(self.actor.hidden_sizes),
        }
