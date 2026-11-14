# Defender commands, completion names and feedback codes.

from typing import Literal, get_args

#only the action types which lead to a job, i.e. does not include "wait".
TargetedAction = Literal["inspect", "isolate", "restore", "reconnect"]

#all action types that can be chosen.
ActionName = Literal["wait", TargetedAction]

DefenderCommand = tuple[ActionName, str | None]

#result returned when action is attempted to be first started at the beginning of the interval.
CommandResult = Literal["accepted", "already_satisfied", "rejected"]

# feedback after a full interval. Either completion (if a job was completed), 
# otherwise submission result (same as CommandResult) or none.
CommandFeedback = Literal["none", "completed", CommandResult]

# This order defines the choice IDs, independently of TOML key order.
TARGETED_ACTIONS: tuple[TargetedAction, ...] = get_args(TargetedAction)


NO_JOB_CODE = 0
JOB_ACTION_CODES = {action: index for index, action in enumerate(TARGETED_ACTIONS, 1)}
COMMAND_FEEDBACK_CODES = {
    "none": 0,
    "completed": 1,
    "accepted": 2,
    "already_satisfied": 3,
    "rejected": 4,
}
