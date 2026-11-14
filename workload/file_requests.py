from collections.abc import Sequence

from world.state import FileRequestResult, WorldState


def build_required_requests(world_config: dict,
                            workload_config: dict) -> list[tuple[str, str]]:
    
    routes = []
    
    for zone in world_config["zones"].values():
        for server_id in zone["servers"]:
            routes.append((zone["employee"], server_id))

    for first, second in world_config["network"]["server_pairs"]:
        routes.append((first, second))
        routes.append((second, first))

    return routes * workload_config["requests"]["per_route_per_interval"]



def run_file_requests(state: WorldState, 
                      world_config: dict,
                      workload_config: dict,
                      *, 
                      required_requests: Sequence[tuple[str, str]] | None = None,) -> list[FileRequestResult]:
    
    results = []
    
    if required_requests is None:
        required_requests = build_required_requests(world_config, workload_config)
    
    for source_id, target_id in required_requests:
        
        source = state.hosts[source_id]
        target = state.hosts[target_id]
        
        # employee is always client in a request.
        source_ready = not source.has_file_service or source.file_service_running
        
        succeeded = (
            not source.isolated
            and not target.isolated
            and source_ready
            and target.has_file_service
            and target.file_service_running
        )
        results.append(FileRequestResult(source_id, target_id, succeeded))

    state.request_results = results
    return results.copy()
