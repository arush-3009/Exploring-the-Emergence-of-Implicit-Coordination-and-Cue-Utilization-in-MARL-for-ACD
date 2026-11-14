from collections.abc import Sequence

import numpy as np

from observations.contracts import DefenderObservation, ObservationVector
from observations.schema import (
    INSPECTION_CATEGORIES,
    JOB_CATEGORIES,
    SERVER_OBSERVATION_FIELDS,
    WORK_CATEGORIES,
    ObservationField,
    observation_feature_names,
    own_observation_fields,
)

__all__ = [
    "INSPECTION_CATEGORIES", "JOB_CATEGORIES", "WORK_CATEGORIES",
    "ObservationEncoder", "encode_defender_observation", "observation_feature_names",
]


def _one_hot(value: int, categories: dict[str, int], field: str) -> list[float]:
    
    if type(value) is not int:
        raise TypeError(f"{field} must be an integer code")
    if value not in categories.values():
        raise ValueError(f"Unknown {field} code: {value!r}")
    
    result = []
    
    for code in categories.values():
        result.append(float(value == code))
        
    return result


def _flag(value: int, field: str) -> float:
    
    if type(value) is not int:
        raise TypeError(f"{field} must be an integer flag")
    if value not in (0, 1):
        raise ValueError(f"{field} must be 0 or 1")
    
    return float(value)


def _scaled_counter(value: int, limit: int, field: str, allow_missing: bool = False) -> float:
    
    if type(value) is not int:
        raise TypeError(f"{field} must be an integer")
    if allow_missing and value == -1:
        return -1.0
    if not 0 <= value <= limit:
        raise ValueError(f"{field} must be between 0 and {limit}")
    
    return value / limit


class ObservationEncoder:

    def __init__(self, server_ids: Sequence[str], max_steps: int, max_job_steps: int) -> None:
        
        for name, limit in (("max_steps", max_steps), ("max_job_steps", max_job_steps)):
            if type(limit) is not int:
                raise TypeError(f"{name} must be an integer")
            if limit < 1:
                raise ValueError(f"{name} must be positive")
        if not server_ids or len(set(server_ids)) != len(server_ids):
            raise ValueError("server_ids must be a nonempty list of unique local IDs")

        self._server_ids = tuple(server_ids)
        self._server_set = frozenset(server_ids)
        self._limits = {"episode": max_steps, "job": max_job_steps}
        self._own_fields = own_observation_fields(len(server_ids))


    def encode(self, observation: DefenderObservation) -> ObservationVector:
        
        if set(observation["servers"]) != self._server_set:
            raise ValueError("Observation servers must match the configured local servers")

        values = self._encode_fields(observation, self._own_fields)
    
        for server_id in self._server_ids:
            values.extend(self._encode_fields(observation["servers"][server_id], SERVER_OBSERVATION_FIELDS))
            
        return np.array(values, dtype=np.float32)


    def _encode_fields(self, source: dict, fields: tuple[ObservationField, ...]) -> list[float]:
        
        values = []
        
        for field in fields:
            value = source[field.key]
            if field.categories is not None:
                values.extend(_one_hot(value, field.categories, field.key))
            elif field.divisor is not None:
                values.append(_scaled_counter(value, self._limits[field.divisor], 
                                              field.key,
                                              allow_missing=field.allow_missing))
            else:
                values.append(_flag(value, field.key))
                
        return values




def encode_defender_observation(observation: DefenderObservation, 
                                server_ids: Sequence[str],
                                max_steps: int, 
                                max_job_steps: int) -> ObservationVector:
    
    return ObservationEncoder(server_ids, max_steps, max_job_steps).encode(observation)
