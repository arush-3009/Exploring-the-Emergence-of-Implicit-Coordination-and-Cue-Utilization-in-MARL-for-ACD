import math
from pathlib import Path

from world.config_io import read_checked_toml


def read_reward_config(path: str | Path, *, world: dict | None = None) -> dict:
    
    config = read_checked_toml(Path(path), "reward", validate_reward_config)
    if world is not None:
        check_reward_zones(config, world)
        
    return config



def check_reward_zones(config: dict, world: dict) -> None:
    unknown = set(config.get("compromise_penalties_by_zone", {})) - set(world["zones"])
    if unknown:
        raise ValueError(f"Unknown reward zones: {sorted(unknown)}")


def validate_reward_config(config: dict) -> None:
    
    if not isinstance(config, dict) or "penalties" not in config or set(config) - {"penalties", "compromise_penalties_by_zone"}:
        raise ValueError("reward needs penalties and optionally compromise_penalties_by_zone")
    
    penalties = config["penalties"]
    expected = {"per_compromised_server", "per_failed_request", "per_inspection"}
    
    if not isinstance(penalties, dict) or set(penalties) != expected:
        raise ValueError(f"penalties must contain exactly {sorted(expected)}")
    
    overrides = config.get("compromise_penalties_by_zone", {})
    if not isinstance(overrides, dict) or any(not isinstance(zone, str) or not zone for zone in overrides):
        raise ValueError("compromise_penalties_by_zone must map zone names to non-negative weights")
    
    weights = list(penalties.items())
    weights.extend(overrides.items())
    
    for name, value in weights:
        if type(value) not in (int, float) or value < 0:
            raise ValueError(f"reward weight {name} must be a non-negative number")
        try:
            finite = math.isfinite(value)
        except OverflowError:
            finite = False
        if not finite:
            raise ValueError(f"reward weight {name} must be finite")
