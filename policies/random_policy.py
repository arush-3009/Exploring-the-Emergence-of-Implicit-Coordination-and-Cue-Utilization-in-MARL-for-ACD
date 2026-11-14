from random import Random

import numpy as np


class RandomPolicy:

    def __init__(self, action_count: int, seed: int) -> None:
        
        if type(action_count) is not int:
            raise TypeError("action_count must be an integer")
        if action_count < 1:
            raise ValueError("action_count must be positive")
        if type(seed) is not int:
            raise TypeError("seed must be an integer")

        self._action_count = action_count
        self._random = Random(seed)
        self._seed = seed

    def __call__(self, observation: np.ndarray) -> int:
        return self._random.randrange(self._action_count)

    def describe(self) -> dict:
        return {"type": "RandomPolicy", "seed": self._seed, "action_count": self._action_count}
