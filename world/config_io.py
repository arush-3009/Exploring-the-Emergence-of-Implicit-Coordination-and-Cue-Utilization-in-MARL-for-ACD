import tomllib
from collections.abc import Callable
from pathlib import Path


def read_checked_toml(path: Path, component: str, validate: Callable[[dict], None]) -> dict:
    try:
        with path.open("rb") as file:
            config = tomllib.load(file)
        validate(config)
    except ValueError as error:
        raise ValueError(f"Invalid {component} configuration in {path}: {error}") from error
    return config


def check_interval_range(value, label: str, max_steps: int) -> None:

    if (not isinstance(value, list) or len(value) != 2
            or any(type(item) is not int for item in value)
            or not 0 <= value[0] <= value[1] < max_steps):
        raise ValueError(f"{label} must be [first, last] with 0 <= first <= last < {max_steps}")
