from collections.abc import Mapping

from world.layout import build_server_partners
from world.state import AttackJob, WorldState


def start_attack_jobs(state: WorldState,
                      world_config: dict,
                      attacker_config: dict,
                      *, 
                      partners: Mapping[str, str] | None = None,) -> dict[str, str]:
   
    
    if partners is None:
        partners = build_server_partners(world_config)

    _validate_existing_jobs(state, partners)

    duration = attacker_config["spread"]["duration_steps"]
    started = {}
    for source_id, target_id in partners.items():
        source = state.hosts[source_id]
        target = state.hosts[target_id]

        # preserve an unfinished attempt and its timer
        if source_id in state.attack_jobs:
            continue
        if not source.compromised or source.isolated:
            continue
        if target.compromised or target.isolated:
            continue
        if not target.has_file_service or not target.file_service_running:
            continue
        if not target.vulnerable:
            continue

        state.attack_jobs[source_id] = AttackJob(
            target=target_id, remaining_steps=duration
        )
        started[source_id] = target_id

    return started


def advance_attack_jobs(state: WorldState, 
                        world_config: dict,
                        *, partners: Mapping[str, str] | None = None) -> dict[str, str]:
   
    if partners is None:
        partners = build_server_partners(world_config)
        
   
    _validate_existing_jobs(state, partners)

    completed = {}
    
    
    for source_id, job in list(state.attack_jobs.items()):
        
        job.remaining_steps -= 1
        
        if job.remaining_steps > 0:
            continue

        source = state.hosts[source_id]
        target = state.hosts[job.target]
        can_compromise = (
            source.compromised
            and not source.isolated
            and not target.compromised
            and not target.isolated
            and target.has_file_service
            and target.file_service_running
            and target.vulnerable
        )
        if can_compromise:
            target.compromised = True
            completed[source_id] = "succeeded"
        else:
            completed[source_id] = "failed"

        del state.attack_jobs[source_id]

    return completed


def _validate_existing_jobs(state: WorldState, partners: Mapping[str, str]) -> None:
    
    for source_id, job in state.attack_jobs.items():
        if not isinstance(source_id, str):
            raise TypeError("Attack source ID must be a string")
        if source_id not in partners:
            raise ValueError(f"Unknown attack source: {source_id!r}")
        if not isinstance(job, AttackJob):
            raise TypeError(f"Attack job for {source_id!r} must be an AttackJob")
        if not isinstance(job.target, str):
            raise TypeError("Attack target ID must be a string")
        if job.target != partners[source_id]:
            raise ValueError(
                f"Attack target must be the paired server of {source_id!r}"
            )
        if type(job.remaining_steps) is not int:
            raise TypeError("Attack remaining_steps must be an integer")
        if job.remaining_steps < 1:
            raise ValueError("An active attack must have at least one remaining step")
