from pathlib import Path

from world.config_io import read_checked_toml


def read_workload_config(path: str | Path) -> dict:
    return read_checked_toml(Path(path), "workload", validate_workload_config)


def validate_workload_config(config: dict) -> None:
    
    if not isinstance(config, dict) or set(config) != {"requests"}:
        raise ValueError("workload must contain only the requests table")
    
    requests = config["requests"]
    if not isinstance(requests, dict) or set(requests) != {"per_route_per_interval"}:
        raise ValueError("requests must contain exactly per_route_per_interval")
    
    count = requests["per_route_per_interval"]
    if type(count) is not int or count < 1:
        raise ValueError("requests.per_route_per_interval must be a positive integer")
