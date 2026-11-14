from pathlib import Path

from world.config_io import check_interval_range, read_checked_toml

MASK_KEYS = ("hide_peer_request_result", "suppress_peer_failures_when_local_available")
WARNING_KEYS = ("false_warnings_per_episode", "miss_share", "interval_range")


def read_observation_config(world_config: dict, path: str | Path) -> dict:
    return read_checked_toml(Path(path), "observation", lambda config: validate_observation_config(config, world_config))


def hidden_peer_request_defenders(observation_config: dict) -> tuple[str, ...]:
    
    return tuple(observation_config.get("masks", {}).get("hide_peer_request_result", []))


def suppressed_peer_failure_defenders(observation_config: dict) -> tuple[str, ...]:

    return tuple(observation_config.get("masks", {}).get("suppress_peer_failures_when_local_available", []))


def validate_observation_config(config: dict, world_config: dict) -> None:
   
    if not isinstance(config, dict) or "monitoring" not in config or not set(config) <= {"monitoring", "masks", "warnings"}:
        raise ValueError("observations must contain the monitoring table and at most a masks table and a warnings table")
    
    monitoring = config["monitoring"]
    keys = {"basic_delay_steps", "extra_information_delay_steps", "extra_detector_zones"}
    
    if not isinstance(monitoring, dict) or set(monitoring) != keys:
        raise ValueError("monitoring must contain exactly basic_delay_steps, extra_information_delay_steps and extra_detector_zones")
    
    for key in ("basic_delay_steps", "extra_information_delay_steps"):
        
        if type(monitoring[key]) is not int or monitoring[key] < 1:
            raise ValueError(f"monitoring.{key} must be a positive integer")

    _check_zone_list(monitoring["extra_detector_zones"], "monitoring.extra_detector_zones", world_config)

    if "masks" in config:
        masks = config["masks"]
        if not isinstance(masks, dict) or not masks or not set(masks) <= set(MASK_KEYS):
            raise ValueError(f"masks must contain one or both of {', '.join(MASK_KEYS)}")
        for key, defenders in masks.items():
            _check_zone_list(defenders, "masks." + key, world_config)
        if set(hidden_peer_request_defenders(config)) & set(suppressed_peer_failure_defenders(config)):
            raise ValueError("masks cannot hide and suppress peer results for the same defender")

    if "warnings" in config:
        _check_warnings(config["warnings"], world_config["episode"]["max_steps"])




def _check_warnings(warnings, max_steps: int) -> None:
    
    if not isinstance(warnings, dict) or set(warnings) != set(WARNING_KEYS):
        raise ValueError(f"warnings must contain exactly {', '.join(WARNING_KEYS)}")
    
    count = warnings["false_warnings_per_episode"]
    if type(count) is not int or count < 0:
        raise ValueError("warnings.false_warnings_per_episode must be an integer of at least 0")
    
    share = warnings["miss_share"]
    if type(share) not in (int, float) or not 0 <= share <= 1:
        raise ValueError("warnings.miss_share must be a number from 0 to 1")
    
    check_interval_range(warnings["interval_range"], "warnings.interval_range", max_steps)




def _check_zone_list(zones, name: str, world_config: dict) -> None:
    if not isinstance(zones, list) or any(not isinstance(zone, str) for zone in zones):
        raise ValueError(f"{name} must be a list of zone IDs")
    if len(zones) != len(set(zones)):
        raise ValueError(f"{name} must not repeat a zone")
    if any(zone not in world_config["zones"] for zone in zones):
        raise ValueError(f"{name} contains an unknown zone")
