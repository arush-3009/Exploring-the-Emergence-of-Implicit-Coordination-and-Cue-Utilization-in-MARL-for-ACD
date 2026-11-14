# Inspect a server on an open warning, Restore it only when the inspection finds it compromised,
# Reconnect once the restore is done. Else, wait.

import numpy as np

from actions.contracts import TARGETED_ACTIONS
from observations.schema import observation_feature_names

WAIT_ACTION_ID = 0


class InspectThenRestore:

    def __init__(self, server_count: int) -> None:

        if type(server_count) is not int:
            raise TypeError("server_count must be an integer")
        if server_count < 1:
            raise ValueError("server_count must be positive")

        self._server_count = server_count

        names = observation_feature_names(server_count)
        position = {}
        for index, name in enumerate(names):
            position[name] = index

        self._observation_size = len(names)

        self._running = []
        self._isolated = []
        self._warning = []
        self._finding_compromised = []
        for server in range(1, server_count + 1):
            self._running.append(position[f"server_{server}.service_running"])
            self._isolated.append(position[f"server_{server}.isolated"])
            self._warning.append(position[f"server_{server}.warning_received"])
            self._finding_compromised.append(position[f"server_{server}.inspection_finding.compromised"])

    def __call__(self, observation: np.ndarray) -> int:

        if len(observation) != self._observation_size:
            raise ValueError(f"observation must have {self._observation_size} entries for "
                             f"{self._server_count} servers, got {len(observation)}")

        for slot in range(self._server_count):
            if observation[self._isolated[slot]] == 1 and observation[self._running[slot]] == 1:
                return self._action_id("reconnect", slot)

        for slot in range(self._server_count):
            if observation[self._finding_compromised[slot]] == 1:
                return self._action_id("restore", slot)

        for slot in range(self._server_count):
            if observation[self._warning[slot]] == 1 and observation[self._isolated[slot]] == 0:
                return self._action_id("inspect", slot)

        return WAIT_ACTION_ID

    def _action_id(self, action: str, slot: int) -> int:
        return 1 + slot * len(TARGETED_ACTIONS) + TARGETED_ACTIONS.index(action)

    def describe(self) -> dict:
        return {"type": "InspectThenRestore", "server_count": self._server_count}
