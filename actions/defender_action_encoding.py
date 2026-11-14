from actions.contracts import TARGETED_ACTIONS, ActionName, DefenderCommand


def build_defender_action_choices(world_config: dict, defender_id: str) -> tuple[tuple[ActionName, str | None], ...]:
    
    if not isinstance(defender_id, str):
        raise TypeError("defender_id must be a string")
    if defender_id not in world_config["zones"]:
        raise ValueError(f"Unknown defender_id: {defender_id!r}")

    #start by adding action choice for "wait"
    choices: list[tuple[ActionName, str | None]] = [("wait", None)]
    
    for server_id in world_config["zones"][defender_id]["servers"]:
        for action in TARGETED_ACTIONS:
            choices.append((action, server_id))
    return tuple(choices)


def decode_action_choice(choices: tuple[DefenderCommand, ...], action_id: int) -> DefenderCommand:
    
    if type(action_id) is not int:
        raise TypeError("action_id must be an integer")
    if not 0 <= action_id < len(choices):
        raise ValueError(f"action_id must be between 0 and {len(choices) - 1}")
    
    return choices[action_id]
