from actions.contracts import (
    TARGETED_ACTIONS,
    ActionName,
    CommandResult,
    TargetedAction,
)
from world.episode_script import outage_active
from world.state import DefenderJob, InspectionFinding, WorldState


def start_defender_action(state: WorldState,
                          action_config: dict,
                          defender_id: str,
                          action: ActionName,
                          target: str | None = None,) -> CommandResult:

    validate_defender_action(state, action_config, defender_id, action, target)
    return start_validated_defender_action(state, action_config, defender_id, action, target)


def start_validated_defender_action(state: WorldState,
                                    action_config: dict, 
                                    defender_id: str,
                                    action: ActionName,
                                    target: str | None = None,) -> CommandResult:
    
    defender = state.defenders[defender_id]

    if defender.job is not None:
        return "rejected"

    if action == "wait":
        return "accepted"

    host = state.hosts[target]
    durations = action_config["duration_steps"]

    #isolate and reconnect when target host already isolated or connected to network should neither disrupt nor change anything.
    if action == "isolate" and host.isolated:
        return "already_satisfied"
    if action == "reconnect" and not host.isolated:
        return "already_satisfied"

    # Construct a targeted job; Wait and already-satisfied commands returned above.
    defender.job = DefenderJob(
        action=action,
        target=target,
        remaining_steps=durations[action],
    )

    # Special handling for restore.
    if action == "restore":
        #cleanup is delayed until completion; taking the service offline is not.
        host.isolated = True
        host.file_service_running = False

    return "accepted"


def validate_defender_action(
    state: WorldState,
    action_config: dict,
    defender_id: str,
    action: ActionName,
    target: str | None = None,
) -> None:

    #errors related to defender_id.
    if not isinstance(defender_id, str):
        raise TypeError("defender_id must be a string")
    if defender_id not in state.defenders:
        raise ValueError(f"Unknown defender_id: {defender_id!r}")

    #errors related to action/action name.
    durations = action_config["duration_steps"]
    if not isinstance(action, str):
        raise TypeError("action must be a string")
    if action not in ("wait", *durations):
        raise ValueError(f"Unknown action: {action!r}")

    #errors related to target.
    if target is not None and not isinstance(target, str):
        raise TypeError("target must be a string or None")
    
    #errors because of different case handling when action is "wait" vs when action is anything else (but still a valid action).
    if action == "wait":
        if target is not None:
            raise ValueError("wait does not take a target")
    else:
        if target is None:
            raise ValueError(f"{action} requires a target")
        if target not in state.hosts:
            raise ValueError(f"Unknown target: {target!r}")
        
        #errors related to defender and target needing to be in same zone and for host to be a file server.
        host = state.hosts[target]
        if host.zone != defender_id:
            raise ValueError(f"Target {target!r} belongs to zone {host.zone!r}")
        if not host.has_file_service:
            raise ValueError(f"Target {target!r} must be a file server")


def advance_defender_jobs(state: WorldState, action_config: dict) -> dict[str, TargetedAction]:
   
    completed = {}
    for defender_id, defender in state.defenders.items():
        
        job = defender.job
        
        #for when defender turns out to be in a state where it is free even after having 
        # started/chosen the action for the time-step in the function start_defender_action.
        # For example, if the defender chose "wait". However, not limited to only "wait". For example, if 
        # the defender tried to choose/start action "isolate"/"reconnect" on an already isolated/reconnected
        # host respectively. 
        if job is None:
            continue

        # error catching for invalid values stored in the job field (DefenderJob) in DefenderState.
        if job.action not in TARGETED_ACTIONS:
            raise ValueError(f"Unknown action in {defender_id!r}'s job: {job.action!r}")
        if type(job.remaining_steps) is not int:
            raise TypeError("Job remaining_steps must be an integer")
        if job.remaining_steps < 1:
            raise ValueError("An active job must have at least one remaining step")

        #accounting for current discrete time-step (of the MDP).
        job.remaining_steps -= 1
        
        #nothing to update if job still going on.
        if job.remaining_steps > 0:
            continue
        
        
        #processing updates for when a job finishes in this discrete time-step of MDP.
        host = state.hosts[job.target]
        
        if job.action == "inspect":
            defender.inspection_findings[job.target] = InspectionFinding(
                compromised=host.compromised,
                completed_step=state.elapsed_steps + 1,
            )
            defender.monitoring_warnings.pop(job.target, None)
        elif job.action == "isolate":
            host.isolated = True
        elif job.action == "restore":
            defender.monitoring_warnings.pop(job.target, None)
            defender.inspection_findings.pop(job.target, None)
            host.compromised = False
            host.file_service_running = not outage_active(state, job.target)
            if action_config["restore"]["patches_server"]:
                host.vulnerable = False
            # Isolation remains; cleanup is not reconnection.
        elif job.action == "reconnect":
            host.isolated = False

        completed[defender_id] = job.action
        #setting defender's job status back to None if this discrete time-step of the MDP finishes job.
        defender.job = None

    return completed
