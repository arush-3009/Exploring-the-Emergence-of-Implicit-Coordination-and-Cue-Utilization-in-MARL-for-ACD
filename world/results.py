from typing import Literal, TypedDict

from actions.contracts import CommandResult, TargetedAction
from observations.contracts import DefenderObservation, ObservationVector
from rewards.contracts import RewardResult


class RequestReport(TypedDict):
    source: str
    target: str
    succeeded: bool


class WarningReport(TypedDict):
    received_step: int


#one server's hidden truth at the end of the interval.
class ServerReport(TypedDict):
    compromised: bool
    isolated: bool
    service_running: bool
    vulnerable: bool


class WorldStepReport(TypedDict):
    elapsed_steps: int
    intrusion: str | None
    outages_started: list[str]
    defender_command_results: dict[str, CommandResult]
    
    # The target's hidden truth just before each accepted targeted start, None for every other defender.
    target_states_at_start: dict[str, ServerReport | None]
    
    defender_completions: dict[str, TargetedAction]
    attacks_started: dict[str, str]
    attack_completions: dict[str, Literal["succeeded", "failed"]]
    request_results: list[RequestReport]
    monitoring_deliveries: dict[str, dict[str, WarningReport]]
    reward: RewardResult
    servers: dict[str, ServerReport]
    episode_finished: bool


class BoundaryResult(TypedDict):
    observations: dict[str, ObservationVector]
    observation_facts: dict[str, DefenderObservation]
    defenders_to_act: tuple[str, ...]
    shared_reward: float | None
    episode_finished: bool
    world_report: WorldStepReport | None
    script: dict
