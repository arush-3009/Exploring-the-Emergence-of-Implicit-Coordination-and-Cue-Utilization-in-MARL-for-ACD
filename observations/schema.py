from dataclasses import dataclass
from typing import Literal

from actions.contracts import COMMAND_FEEDBACK_CODES, JOB_ACTION_CODES, NO_JOB_CODE

JOB_CATEGORIES = {"no_job": NO_JOB_CODE, **JOB_ACTION_CODES}
WORK_CATEGORIES = {"unknown": -1, "failed": 0, "succeeded": 1}
INSPECTION_CATEGORIES = {"unknown": -1, "clean": 0, "compromised": 1}


@dataclass(frozen=True)
class ObservationField:
    #key-name in raw observation dictionary.
    key: str
    #name of observation field in observation numeric encoding.
    name: str
    #categories of field (implies one-hot encoding amongst these categories).
    categories: dict[str, int] | None = None
    #value to divide by.
    divisor: Literal["episode", "job"] | None = None
    #True if -1 is allowed as representation of something that is unknown at a given time.
    allow_missing: bool = False

    def feature_names(self) -> tuple[str, ...]:
        
        #for when there are multiple categories (one-hot) in the same raw observation field.
        if self.categories is not None:
            return tuple(f"{self.name}.{category}" for category in self.categories)
        
        return (self.name,)


# defender's general observation fields
def own_observation_fields(server_count: int) -> tuple[ObservationField, ...]:
    
    if type(server_count) is not int:
        raise TypeError("server_count must be an integer")
    if server_count < 1:
        raise ValueError("server_count must be positive")
    
    target_categories = {"none": 0}
    target_categories.update({f"server_{i}": i for i in range(1, server_count + 1)})

    return (ObservationField("elapsed_steps", "elapsed_fraction", divisor="episode"),
            ObservationField("extra_detector_available", "extra_detector_available"),
            #then, add to the array the one-hot encoding representation of the defender's ongoing job's action
            ObservationField("job_action", "job_action", JOB_CATEGORIES),
            #then, add to the array the one-hot encoding representation of the defender's ongoing job's target
            ObservationField("job_target", "job_target", target_categories),
            #then, the scaled version for the remaining steps of the defender's job.
            ObservationField("job_remaining_steps", "job_remaining_fraction", divisor="job"),
            #then, the one-hot encoding representation of the last_command_feedback the defender got.
            ObservationField("last_command_feedback", "last_command_feedback", COMMAND_FEEDBACK_CODES),)


# Per-Server Observation Fields
SERVER_OBSERVATION_FIELDS = (
    ObservationField("service_running", "service_running"),
    ObservationField("isolated", "isolated"),
    ObservationField("employee_request_result", "employee_request_result", WORK_CATEGORIES),
    ObservationField("peer_request_result", "peer_request_result", WORK_CATEGORIES),
    ObservationField("warning_received", "warning_received"),
    ObservationField("warning_age", "warning_age_fraction", divisor="episode", allow_missing=True),
    ObservationField("inspection_finding", "inspection_finding", INSPECTION_CATEGORIES),
    ObservationField("inspection_age", "inspection_age_fraction", divisor="episode", allow_missing=True),
)


def observation_feature_names(server_count: int) -> tuple[str, ...]:
    
    names = []
    
    for field in own_observation_fields(server_count):
        names.extend(field.feature_names())
        
    for index in range(1, server_count + 1):
        for field in SERVER_OBSERVATION_FIELDS:
            names.extend(f"server_{index}.{name}" for name in field.feature_names())    
            
    return tuple(names)
