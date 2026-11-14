from actions.contracts import COMMAND_FEEDBACK_CODES, JOB_ACTION_CODES, NO_JOB_CODE
from observations.contracts import DefenderObservation
from observations.observation_config import (
    hidden_peer_request_defenders,
    suppressed_peer_failure_defenders,
)
from world.layout import WorldLayout
from world.state import WorldState


def build_defender_observation(state: WorldState, 
                               world_config: dict, 
                               observation_config: dict, 
                               defender_id: str,
                               *,
                               layout: WorldLayout | None = None) -> DefenderObservation:
   
    
    #raise errors due to invalid input
    if not isinstance(defender_id, str):
        raise TypeError("defender_id must be a string")
    if defender_id not in state.defenders:
        raise ValueError(f"Unknown defender_id: {defender_id!r}")

    defender = state.defenders[defender_id]
    
    if layout is None:
        layout = WorldLayout.from_config(world_config)
        
    employee_id = layout.employees[defender_id]
    server_ids = layout.servers[defender_id]
    
    job = defender.job
    
    if job is not None and job.target not in layout.server_slots[defender_id]:
        raise ValueError(f"{job.target!r} is not in list")
    
    observation = {
        "elapsed_steps": state.elapsed_steps,
        "extra_detector_available": int(defender_id in observation_config["monitoring"]["extra_detector_zones"]),
        "job_action": JOB_ACTION_CODES[job.action] if job is not None else NO_JOB_CODE,
        "job_target": layout.server_slots[defender_id][job.target] if job is not None else 0,
        "job_remaining_steps": job.remaining_steps if job is not None else 0,
        "last_command_feedback": COMMAND_FEEDBACK_CODES[defender.last_command_feedback],
    }

    partners = layout.partners
    hide_peer_results = defender_id in hidden_peer_request_defenders(observation_config)
    suppress_peer_failures = defender_id in suppressed_peer_failure_defenders(observation_config)
   
    work_results = {(result.source, result.target): int(result.succeeded) for result in state.request_results}
    
    local_servers = {}
    
    for server_id in server_ids:
        
        host = state.hosts[server_id]
        
        warning = defender.monitoring_warnings.get(server_id)
        finding = defender.inspection_findings.get(server_id)

        peer_result = work_results[(server_id, partners[server_id])] if work_results else -1
        if hide_peer_results:
            peer_result = -1
        elif suppress_peer_failures and peer_result == 0 and host.file_service_running and not host.isolated:
            peer_result = 1
        
        local_servers[server_id] = {
            
            "service_running": int(host.file_service_running),
            
            "isolated": int(host.isolated),
            
            "employee_request_result": (work_results[(employee_id, server_id)] if work_results else -1),
            
            "peer_request_result": peer_result,
            
            "warning_received": int(warning is not None),
            
            "warning_age": (_evidence_age(state.elapsed_steps, warning.received_step) if warning is not None else -1),
            
            "inspection_finding": int(finding.compromised) if finding is not None else -1,
            
            "inspection_age": (_evidence_age(state.elapsed_steps, finding.completed_step) if finding is not None else -1),
        }   
        
    observation["servers"] = local_servers
    return observation


def _evidence_age(boundary_step: int, evidence_step: int) -> int:

    if type(evidence_step) is not int:
        raise TypeError("Evidence boundary must be an integer")
    if not 0 <= evidence_step <= boundary_step:
        raise ValueError("Evidence boundary must not be negative or in the future")
    
    return boundary_step - evidence_step
