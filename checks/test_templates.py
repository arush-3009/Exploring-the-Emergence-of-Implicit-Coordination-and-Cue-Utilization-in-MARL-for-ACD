import re
import tomllib
from pathlib import Path

from studies.definitions import MASKS, SENDER_WORLD, STUDIES

ROOT = Path(__file__).resolve().parents[1]
SETTINGS_FOLDERS = ("checks/test-world", "checks/test-settings", "studies/settings", "worlds/*")

COMPONENTS = {
    "world": ("world/world_config.template.toml", "world_config.toml"),
    "actions": ("actions/action_config.template.toml", "action_config.toml"),
    "attacker": ("attacker/attacker_config.template.toml", "attacker_config.toml"),
    "workload": ("workload/workload_config.template.toml", "workload_config.toml"),
    "observations": ("observations/observation_config.template.toml", "observation_config.toml"),
    "rewards": ("rewards/reward_config.template.toml", "reward_config.toml"),
    "training": ("learning/training_config.template.toml", "training_config.toml"),
    "imitation": ("learning/imitation_config.template.toml", "imitation_config.toml"),
}


def template_keys(path):
    keys = []
    table = ""
    for line in path.read_text().splitlines():
        header = re.match(r"^#\s*\[([^\]]+)\]\s*$", line)
        key = re.match(r"^#\s*([a-z_]+|<[a-z]+>)\s*=", line)
        if header:
            table = header.group(1)
        elif key:
            keys.append(f"{table}.{key.group(1)}")
    return keys


def used_keys(data, prefix=""):
    keys = []
    for name, value in data.items():
        if isinstance(value, dict):
            keys.extend(used_keys(value, f"{prefix}{name}."))
        else:
            keys.append(f"{prefix}{name}")
    return keys


def listed(key, template):
    for candidate in template:
        parts, wanted = candidate.split("."), key.split(".")
        if len(parts) == len(wanted):
            matches = True
            for part, name in zip(parts, wanted, strict=True):
                if not part.startswith("<") and part != name:
                    matches = False
            if matches:
                return True
    return False


def test_templates_set_no_value_and_list_every_key_in_use():
    overrides = {**SENDER_WORLD}
    for mask in MASKS.values():
        overrides.update(mask)
    for study in STUDIES.values():
        overrides.update(study.training_overrides)

    for component, (template_path, file_name) in COMPONENTS.items():
        template = ROOT / template_path
        assert tomllib.loads(template.read_text()) == {}
        keys = template_keys(template)
        assert keys, template_path

        used = []
        for folders in SETTINGS_FOLDERS:
            for path in ROOT.glob(f"{folders}/{file_name}"):
                used.extend(used_keys(tomllib.loads(path.read_text())))
        for dotted in overrides:
            if dotted.split(".")[0] == component:
                used.append(dotted.split(".", 1)[1])
        assert used, component
        for key in used:
            assert listed(key, keys), f"{key} is used but missing from {template_path}"
