from pathlib import Path

from world.config_io import read_checked_toml


def read_attacker_config(path: str | Path) -> dict:
    return read_checked_toml(Path(path), "attacker", validate_attacker_config)


def validate_attacker_config(config: dict) -> None:
    
    
    if not isinstance(config, dict) or set(config) != {"spread"}:
        raise ValueError("attacker must contain only the spread table")
    
    spread = config["spread"]
    
    if not isinstance(spread, dict) or set(spread) != {"duration_steps"}:
        raise ValueError("spread must contain exactly duration_steps")
    
    duration = spread["duration_steps"]
    if type(duration) is not int or duration < 1:
        raise ValueError("spread.duration_steps must be a positive integer")
