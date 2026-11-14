import numpy as np

WAIT_ACTION_ID = 0

class AlwaysWait:

    def __call__(self, observation: np.ndarray) -> int:
        return WAIT_ACTION_ID

    def describe(self) -> dict:
        return {"type": "AlwaysWait"}
