# Named local observations and their numeric representations.

from typing import TypedDict

import numpy as np
from numpy.typing import NDArray

ObservationVector = NDArray[np.float32]


class ServerObservation(TypedDict):
    service_running: int
    isolated: int
    employee_request_result: int
    peer_request_result: int
    warning_received: int  # Outstanding warning; completed Inspect/Restore clears it.
    warning_age: int
    inspection_finding: int
    inspection_age: int


class DefenderObservation(TypedDict):
    elapsed_steps: int
    extra_detector_available: int
    job_action: int
    job_target: int
    job_remaining_steps: int
    last_command_feedback: int
    servers: dict[str, ServerObservation]
