from typing import TypedDict


class RewardResult(TypedDict):
    compromised_server_count: int
    compromise_cost_by_zone: dict[str, float]
    failed_request_count: int
    inspection_start_count: int
    compromise_cost: float
    request_failure_cost: float
    inspection_cost: float
    shared_reward: float
