from world.state import MonitoringWarning, WorldState


def update_monitoring(state: WorldState, observation_config: dict) -> dict[str, dict[str, MonitoringWarning]]:
    
    for host_id, started_step in state.compromise_started_steps.items():
        if not isinstance(host_id, str):
            raise TypeError("Monitored host ID must be a string")
        if host_id not in state.hosts or not state.hosts[host_id].has_file_service:
            raise ValueError(f"Monitored host must be an existing server: {host_id!r}")
        if type(started_step) is not int:
            raise TypeError("Compromise start boundary must be an integer")
        if not 0 <= started_step <= state.elapsed_steps:
            raise ValueError("Compromise start boundary must be in the elapsed past")

    boundary_step = state.elapsed_steps + 1
    monitoring = observation_config["monitoring"]
    delivered = {defender_id: {} for defender_id in state.defenders}

    for host_id, host in state.hosts.items():
        if not host.has_file_service:
            continue

        if not host.compromised:
            state.compromise_started_steps.pop(host_id, None)
            continue

        if host_id not in state.compromise_started_steps:
            state.compromise_started_steps[host_id] = boundary_step

        if host_id in state.script.missed_servers:
            continue

        infection_age = boundary_step - state.compromise_started_steps[host_id]
        basic_due = infection_age == monitoring["basic_delay_steps"]
        extra_due = (host.zone in monitoring["extra_detector_zones"] 
                     and 
                     infection_age == monitoring["extra_information_delay_steps"])
        if not (basic_due or extra_due):
            continue

        warning = MonitoringWarning(received_step=boundary_step)
        state.defenders[host.zone].monitoring_warnings[host_id] = warning
        delivered[host.zone][host_id] = warning

    for false_warning in state.script.false_warnings:
        if false_warning.interval == state.elapsed_steps:
            zone = state.hosts[false_warning.server].zone
            warning = MonitoringWarning(received_step=boundary_step)
            state.defenders[zone].monitoring_warnings[false_warning.server] = warning
            delivered[zone][false_warning.server] = warning

    return delivered
