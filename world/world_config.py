# Invalid configuration data consistently raises ValueError, including bad types.
# ruff: noqa: TRY004

from pathlib import Path

from world.config_io import check_interval_range, read_checked_toml


def read_world_config(path: str | Path) -> dict:
    return read_checked_toml(Path(path), "world", validate_world_config)




def _check_intrusion(intrusion: dict, max_steps: int) -> None:
    if not intrusion["servers"]:
        raise ValueError("intrusion.servers must name at least one server")

    check_interval_range(intrusion["start_interval_range"], "intrusion.start_interval_range", max_steps)

    share = intrusion["clean_episode_share"]
    if type(share) not in (int, float) or not 0 <= share <= 1:
        raise ValueError("intrusion.clean_episode_share must be a number from 0 to 1")


def _check_outages(outages: dict, max_steps: int) -> None:
    if not outages["servers"]:
        raise ValueError("outages.servers must name at least one server")

    if type(outages["per_episode"]) is not int or outages["per_episode"] < 0:
        raise ValueError("outages.per_episode must be an integer of at least 0")
    if type(outages["duration_steps"]) is not int or outages["duration_steps"] < 1:
        raise ValueError("outages.duration_steps must be a positive integer")

    check_interval_range(outages["interval_range"], "outages.interval_range", max_steps)


def _check_keys(value: dict, expected: set[str], label: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a table of settings")
    missing = expected - value.keys()
    unknown = value.keys() - expected
    if missing or unknown:
        raise ValueError(
            f"{label}: missing keys {sorted(missing)}; "
            f"unknown keys {sorted(map(str, unknown))}"
        )


def _check_id(value: str, label: str) -> None:
    if not isinstance(value, str) or not value.strip() or value != value.strip():
        raise ValueError(f"{label} must be nonempty text with no surrounding spaces")


def _check_id_list(values: list[str], label: str) -> None:
    if not isinstance(values, list):
        raise ValueError(f"{label} must be a list of IDs")
    for value in values:
        _check_id(value, label)
    if len(set(values)) != len(values):
        raise ValueError(f"{label} must not contain duplicate IDs")
    
    
    
    
    

def validate_world_config(config: dict) -> None:
    
    
    tables = {"episode", "zones", "network", "servers", "initial"}
    
    if "intrusion" in config:
        tables.add("intrusion")
        _check_keys(config["intrusion"], {"servers", "start_interval_range", "clean_episode_share"}, "intrusion")
        
    if "outages" in config:
        tables.add("outages")
        _check_keys(config["outages"], {"per_episode", "duration_steps", "interval_range", "servers"}, "outages")
        
        
    _check_keys(config, tables, "world")
    _check_keys(config["episode"], {"max_steps"}, "episode")
    _check_keys(config["network"], {"server_pairs"}, "network")
    _check_keys(config["servers"], {"vulnerable_servers"}, "servers")
    _check_keys(config["initial"],
                {"compromised_servers", "isolated_servers", "servers_with_stopped_services"},
                "initial",)

    max_steps = config["episode"]["max_steps"]
    
    
    if type(max_steps) is not int or max_steps < 1:
        raise ValueError("episode.max_steps must be a positive integer")

    zones = config["zones"]
    if not isinstance(zones, dict) or len(zones) != 2:
        raise ValueError("zones must contain exactly two zone tables.")

    host_ids = set()
    server_zones = {}
    for zone_id, zone in zones.items():
        _check_id(zone_id, "zone name")
        label = f"zones.{zone_id}"
        _check_keys(zone, {"employee", "servers"}, label)
        _check_id(zone["employee"], f"{label}.employee")
        _check_id_list(zone["servers"], f"{label}.servers")
        if len(zone["servers"]) != 3:
            raise ValueError(f"{label}.servers must contain three servers.")

        for host_id in [zone["employee"], *zone["servers"]]:
            if host_id in host_ids:
                raise ValueError(f"{label}: host ID {host_id!r} is used more than once")
            host_ids.add(host_id)
        for server_id in zone["servers"]:
            server_zones[server_id] = zone_id


    selections = {"servers.vulnerable_servers": config["servers"]["vulnerable_servers"]}
    
    for key, values in config["initial"].items():
        selections[f"initial.{key}"] = values
        
    if "intrusion" in config:
        selections["intrusion.servers"] = config["intrusion"]["servers"]
        
    if "outages" in config:
        selections["outages.servers"] = config["outages"]["servers"]
        
    for label, values in selections.items():
        _check_id_list(values, label)
        for server_id in values:
            if server_id not in server_zones:
                raise ValueError(f"{label}: {server_id!r} is not a declared server")



    pairs = config["network"]["server_pairs"]
    if not isinstance(pairs, list):
        raise ValueError("network.server_pairs must be a list of pairs")
    
    paired_servers = set()
    for index, pair in enumerate(pairs):
        label = f"network.server_pairs[{index}]"
        _check_id_list(pair, label)
        if len(pair) != 2:
            raise ValueError(f"{label} must contain two distinct server IDs")
        for server_id in pair:
            if server_id not in server_zones:
                raise ValueError(f"{label}: {server_id!r} is not a declared server")
            if server_id in paired_servers:
                raise ValueError(
                    f"{label}: {server_id!r} already belongs to another pair"
                )
        if server_zones[pair[0]] == server_zones[pair[1]]:
            raise ValueError(f"{label} must connect servers in different zones")
        paired_servers.update(pair)
    if paired_servers != set(server_zones):
        raise ValueError("network.server_pairs must pair every server exactly once")

    if "intrusion" in config:
        _check_intrusion(config["intrusion"], max_steps)
    if "outages" in config:
        _check_outages(config["outages"], max_steps)
