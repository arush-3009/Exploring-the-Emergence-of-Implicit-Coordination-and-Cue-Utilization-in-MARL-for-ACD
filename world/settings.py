from copy import deepcopy
from pathlib import Path

from actions.action_config import read_action_config, validate_action_config
from attacker.attacker_config import read_attacker_config, validate_attacker_config
from observations.observation_config import (
    read_observation_config,
    validate_observation_config,
)
from rewards.reward_config import (
    check_reward_zones,
    read_reward_config,
    validate_reward_config,
)
from workload.workload_config import read_workload_config, validate_workload_config
from world.world_config import read_world_config, validate_world_config

SETTINGS_FILES = {"world": "world_config.toml",
                  "actions": "action_config.toml",
                  "attacker": "attacker_config.toml",
                  "workload": "workload_config.toml",
                  "observations": "observation_config.toml",
                  "rewards": "reward_config.toml"}


def load_world_settings(world_folder: str | Path) -> dict:

    folder = Path(world_folder)

    names = []
    for path in folder.glob("*.toml"):
        names.append(path.name)
        
    if sorted(names) != sorted(SETTINGS_FILES.values()):
        raise ValueError(f"{folder} must hold exactly {sorted(SETTINGS_FILES.values())}, it holds {sorted(names)}")

    world = read_world_config(folder / "world_config.toml")

    return {"world": world,
            "actions": read_action_config(folder / "action_config.toml"),
            "attacker": read_attacker_config(folder / "attacker_config.toml"),
            "workload": read_workload_config(folder / "workload_config.toml"),
            "observations": read_observation_config(world, folder / "observation_config.toml"),
            "rewards": read_reward_config(folder / "reward_config.toml", world=world)}



def apply_overrides(settings: dict, overrides: dict) -> dict:

    result = deepcopy(settings)

    for dotted, value in overrides.items():
        names = dotted.split(".")
        table = result
        for name in names[:-1]:
            table = table.setdefault(name, {})
        table[names[-1]] = deepcopy(value)

    if set(result) != set(SETTINGS_FILES):
        raise ValueError(f"settings must hold exactly {sorted(SETTINGS_FILES)}, not {sorted(result)}")
    
    
    validate_world_config(result["world"])
    validate_action_config(result["actions"])
    validate_attacker_config(result["attacker"])
    validate_workload_config(result["workload"])
    validate_observation_config(result["observations"], result["world"])
    validate_reward_config(result["rewards"])
    check_reward_zones(result["rewards"], result["world"])

    return result
