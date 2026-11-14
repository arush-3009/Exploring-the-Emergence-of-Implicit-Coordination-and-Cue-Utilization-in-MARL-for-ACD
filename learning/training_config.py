from pathlib import Path

from world.config_io import read_checked_toml


def read_training_config(path: str | Path) -> dict:
    return read_checked_toml(Path(path), "training", validate_training_config)


def validate_training_config(config: dict) -> None:
    
    required = {"networks", "advantages", "ppo", "training"}
    
    if set(config) - {"fixed_defenders"} != required:
        raise ValueError("training needs networks, advantages, ppo and training; optional fixed_defenders")
    
    fixed = config.get("fixed_defenders", {})
    if not isinstance(fixed, dict) or any(mode != "greedy" for mode in fixed.values()):
        raise ValueError("fixed_defenders maps defender IDs to 'greedy'")
    
    if set(config["networks"]) != {"hidden_sizes"}:
        raise ValueError("networks must contain exactly hidden_sizes")
    if set(config["advantages"]) != {"gamma", "gae_lambda"}:
        raise ValueError("advantages must contain exactly gamma and gae_lambda")
    
    ppo_keys = {"actor_learning_rate", "critic_learning_rate", "clip_epsilon", "epochs", "minibatch_size", "entropy_coefficient"}
    if set(config["ppo"]) != ppo_keys:
        raise ValueError(f"ppo must contain exactly {', '.join(sorted(ppo_keys))}")
    
    
    training_keys = {"episodes_per_iteration", "iterations"}
    if set(config["training"]) != training_keys:
        raise ValueError(f"training must contain exactly {', '.join(sorted(training_keys))}")


    hidden_sizes = config["networks"]["hidden_sizes"]
    if not isinstance(hidden_sizes, list) or any(type(size) is not int or size < 1 for size in hidden_sizes):
        raise ValueError("networks.hidden_sizes must be a list of positive integers")

    for key in ("gamma", "gae_lambda"):
        value = config["advantages"][key]
        if not isinstance(value, int | float) or not 0 <= value <= 1:
            raise ValueError(f"advantages.{key} must be a number from 0 to 1")

    ppo = config["ppo"]
    for key in ("actor_learning_rate", "critic_learning_rate"):
        if not isinstance(ppo[key], int | float) or ppo[key] <= 0:
            raise ValueError(f"ppo.{key} must be a positive number")
        
    if not isinstance(ppo["clip_epsilon"], int | float) or not 0 < ppo["clip_epsilon"] < 1:
        raise ValueError("ppo.clip_epsilon must be a number between 0 and 1")

    if not isinstance(ppo["entropy_coefficient"], int | float) or ppo["entropy_coefficient"] < 0:
        raise ValueError("ppo.entropy_coefficient must be a number of at least 0")
    
    for key in ("epochs", "minibatch_size"):
        if type(ppo[key]) is not int or ppo[key] < 1:
            raise ValueError(f"ppo.{key} must be a positive integer")

    for key in sorted(training_keys):
        if type(config["training"][key]) is not int or config["training"][key] < 1:
            raise ValueError(f"training.{key} must be a positive integer")
