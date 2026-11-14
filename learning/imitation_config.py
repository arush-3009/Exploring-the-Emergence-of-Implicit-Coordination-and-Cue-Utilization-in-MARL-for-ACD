from pathlib import Path

from learning.imitation import TEACHERS
from world.config_io import read_checked_toml


def read_imitation_config(path: str | Path) -> dict:
    
    return read_checked_toml(Path(path), "imitation", validate_imitation_config)


def validate_imitation_config(config: dict) -> None:

    if set(config) != {"teacher", "actor_fit", "critic_fit"}:
        raise ValueError("imitation must contain exactly the teacher, actor_fit and critic_fit tables")

    if set(config["teacher"]) != {"rule", "episodes"}:
        raise ValueError("teacher must contain exactly rule and episodes")

    if config["teacher"]["rule"] not in TEACHERS:
        raise ValueError(f"teacher.rule must be one of {list(TEACHERS)}")

    actor_keys = {"epochs", "learning_rate", "minibatch_size", "action_target_weight", "wait_target_weight"}
    if set(config["actor_fit"]) - {"restore_target_weight"} != actor_keys:
        raise ValueError(f"actor_fit must contain {', '.join(sorted(actor_keys))}, optionally restore_target_weight")
    
    
    if (config["teacher"]["rule"] == "inspect-then-restore-prob-restore-weakened"
            and "restore_target_weight" not in config["actor_fit"]):
        raise ValueError("The weakened-Restore teacher requires actor_fit.restore_target_weight")

    critic_keys = {"epochs", "learning_rate", "minibatch_size"}
    if set(config["critic_fit"]) != critic_keys:
        raise ValueError(f"critic_fit must contain exactly {', '.join(sorted(critic_keys))}")

    if type(config["teacher"]["episodes"]) is not int or config["teacher"]["episodes"] < 1:
        raise ValueError("teacher.episodes must be a positive integer")

    for table in ("actor_fit", "critic_fit"):
        for key in ("epochs", "minibatch_size"):
            if type(config[table][key]) is not int or config[table][key] < 1:
                raise ValueError(f"{table}.{key} must be a positive integer")

        learning_rate = config[table]["learning_rate"]
        if not isinstance(learning_rate, int | float) or learning_rate <= 0:
            raise ValueError(f"{table}.learning_rate must be a positive number")

    probability_keys = ["action_target_weight", "wait_target_weight"]
    if "restore_target_weight" in config["actor_fit"]:
        probability_keys.append("restore_target_weight")
        
    for key in probability_keys:
        value = config["actor_fit"][key]
        
        if not isinstance(value, int | float) or not 0 < value <= 1:
            raise ValueError(f"actor_fit.{key} must be a number above 0 and at most 1")
