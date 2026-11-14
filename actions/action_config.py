from pathlib import Path

from actions.contracts import TARGETED_ACTIONS
from world.config_io import read_checked_toml


def read_action_config(path: str | Path) -> dict:
    return read_checked_toml(Path(path), "action", validate_action_config)


def validate_action_config(config: dict) -> None:
    
    if not isinstance(config, dict) or set(config) != {"duration_steps", "restore"}:
        raise ValueError("actions must contain exactly the duration_steps and restore tables")
    
    durations = config["duration_steps"]
    expected = set(TARGETED_ACTIONS)
    
    if not isinstance(durations, dict) or set(durations) != expected:
        raise ValueError(
            "duration_steps must contain exactly inspect, isolate, restore and reconnect"
        )
        
    for action, duration in durations.items():
        if type(duration) is not int or duration < 1:
            raise ValueError(f"duration_steps.{action} must be a positive integer")

    restore = config["restore"]
    if not isinstance(restore, dict) or set(restore) != {"patches_server"} or type(restore["patches_server"]) is not bool:
        raise ValueError("restore must contain only patches_server, true or false")
