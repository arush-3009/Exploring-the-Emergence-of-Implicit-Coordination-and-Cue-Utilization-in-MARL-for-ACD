from math import isfinite

from rewards.contracts import RewardResult
from world.state import WorldState


def calculate_reward(state: WorldState, reward_config: dict, inspection_start_count: int) -> RewardResult:

    if not state.request_results:
        raise ValueError("Reward requires workload results; run a full step first")
    if type(inspection_start_count) is not int or inspection_start_count < 0:
        raise ValueError("inspection_start_count must be a non-negative integer")

    compromised_by_zone = {}
    for zone in state.defenders:
        compromised_by_zone[zone] = 0
    for host in state.hosts.values():
        if host.has_file_service and host.compromised:
            compromised_by_zone[host.zone] += 1
    compromised_server_count = sum(compromised_by_zone.values())
    failed_request_count = sum(not result.succeeded for result in state.request_results)

    penalties = reward_config["penalties"]
    
    overrides = reward_config.get("compromise_penalties_by_zone", {})
    compromise_cost_by_zone = {}
    for zone, count in compromised_by_zone.items():
        weight = overrides.get(zone, penalties["per_compromised_server"])
        compromise_cost_by_zone[zone] = weight * count
    compromise_cost = sum(compromise_cost_by_zone.values())
    request_failure_cost = penalties["per_failed_request"] * failed_request_count
    inspection_cost = penalties["per_inspection"] * inspection_start_count
    
    shared_reward = 0.0 - compromise_cost - request_failure_cost - inspection_cost
    
    if not isfinite(shared_reward):
        raise ValueError("Reward overflowed; reduce the configured penalty weights")

    return {
        "compromised_server_count": compromised_server_count,
        "compromise_cost_by_zone": compromise_cost_by_zone,
        "failed_request_count": failed_request_count,
        "inspection_start_count": inspection_start_count,
        "compromise_cost": compromise_cost,
        "request_failure_cost": request_failure_cost,
        "inspection_cost": inspection_cost,
        "shared_reward": shared_reward,
    }
