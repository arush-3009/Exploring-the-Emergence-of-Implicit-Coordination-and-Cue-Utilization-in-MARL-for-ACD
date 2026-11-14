from dataclasses import dataclass

from policies.always_wait import AlwaysWait
from policies.inspect_then_restore import InspectThenRestore
from policies.random_policy import RandomPolicy
from policies.restore_reconnect_only_when_helpful import RestoreReconnectOnlyWhenHelpful

WORLDS = ("reliable-warnings",
          "one-false-warning",
          "two-false-warnings",
          "one-false-warning-missed-warnings",
          "one-false-warning-missed-warnings-outages")



MASKS = {"cue-hidden-unknown": {"observations.masks.hide_peer_request_result": ["B"]},
         "cue-hidden-failures-suppressed": {"observations.masks.suppress_peer_failures_when_local_available": ["B"]}}



CONTROLS = {"cue-hidden-unknown-at-evaluation": MASKS["cue-hidden-unknown"],
            "cue-hidden-failures-suppressed-at-evaluation": MASKS["cue-hidden-failures-suppressed"]}



RULES = {"always-wait": AlwaysWait,
         "inspect-teacher": InspectThenRestore,
         "restore-teacher": RestoreReconnectOnlyWhenHelpful,
         "random": RandomPolicy}


A_WAITS_BASELINE = "a-waits-with-fixed-b"

# In every sender world A's own infections cost nothing.
SENDER_WORLD = {"rewards.compromise_penalties_by_zone.A": 0.0}



@dataclass(frozen=True)
class Study:
    number: int
    folder: str
    kind: str  # "receiver" or "sender"
    arms: dict
    world_overrides: dict
    start: dict
    fixed: tuple  # defenders loaded and never updated
    training_overrides: dict
    defender_imitation_overrides: dict  # per defender
    baselines: tuple
    worlds: tuple = WORLDS
    seeds: tuple = (0, 1, 2, 3, 4)
    evaluation_seeds: tuple = (2001, 2002)
    episodes_per_seed: int = 1000
    controls: tuple = tuple(CONTROLS)


RULE_BASELINES = tuple(RULES)
SENDER_ARMS = {"cue-visible": {}, "cue-hidden-failures-suppressed": MASKS["cue-hidden-failures-suppressed"]}

STUDIES = {
    
    1: Study(number=1, folder="study-1-receiver-cue-utilization", kind="receiver",
             arms={"cue-visible": {}, "cue-hidden-unknown": MASKS["cue-hidden-unknown"]},
             world_overrides={}, start={"A": "warm-start", "B": "warm-start"}, fixed=(),
             training_overrides={}, defender_imitation_overrides={}, baselines=RULE_BASELINES),
    
    
    2: Study(number=2, folder="study-2-sender-joint-teacher-start", kind="sender",
             arms=SENDER_ARMS, world_overrides=SENDER_WORLD, start={"A": "warm-start", "B": "warm-start"}, fixed=(),
             training_overrides={},
             defender_imitation_overrides={"A": {"actor_fit.restore_target_weight": 0.6}},
             baselines=RULE_BASELINES),
    
    
    3: Study(number=3, folder="study-3-sender-random-a-fixed-b", kind="sender",
             arms=SENDER_ARMS, world_overrides=SENDER_WORLD, start={"A": "random", "B": "study-1-team"},
             fixed=("B",), training_overrides={}, defender_imitation_overrides={},
             baselines=(*RULE_BASELINES, A_WAITS_BASELINE)),
    
    
    4: Study(number=4, folder="study-4-sender-teacher-a-fixed-b", kind="sender",
             arms=SENDER_ARMS, world_overrides=SENDER_WORLD, start={"A": "warm-start", "B": "study-1-team"},
             fixed=("B",),
             training_overrides={"imitation.teacher.rule": "inspect-then-restore-prob-restore-weakened",
                                 "imitation.actor_fit.restore_target_weight": 0.6},
             defender_imitation_overrides={},
             baselines=(*RULE_BASELINES, A_WAITS_BASELINE)),
    
    
    5: Study(number=5, folder="study-5-sender-inherited-a-fixed-b", kind="sender",
             arms=SENDER_ARMS, world_overrides=SENDER_WORLD, start={"A": "study-1-team", "B": "study-1-team"},
             fixed=("B",), training_overrides={}, defender_imitation_overrides={},
             baselines=(*RULE_BASELINES, A_WAITS_BASELINE)),
}


def apply_dotted_overrides(table: dict, overrides: dict) -> None:

    for dotted, value in overrides.items():

        names = dotted.split(".")
        target = table

        for name in names[:-1]:
            target = target[name]

        target[names[-1]] = value



TRAINING_SETTINGS = {"networks": {"hidden_sizes": [64, 64]},
                     
                     "advantages": {"gamma": 0.99, "gae_lambda": 0.95},
                     
                     "ppo": {"actor_learning_rate": 0.0003, 
                             "critic_learning_rate": 0.01, 
                             "clip_epsilon": 0.2,
                             "epochs": 4,
                             "minibatch_size": 64, 
                             "entropy_coefficient": 0.001},
                     
                     "training": {"episodes_per_iteration": 16, "iterations": 3000}}


IMITATION_SETTINGS = {"teacher": {"rule": "inspect-then-restore", "episodes": 600},
                      
                      "actor_fit": {"epochs": 300,
                                    "learning_rate": 0.001,
                                    "minibatch_size": 256,
                                    "action_target_weight": 0.95,
                                    "wait_target_weight": 0.6},
                      
                      "critic_fit": {"epochs": 30, "learning_rate": 0.001, "minibatch_size": 256}}



SMOKE = {"world": "one-false-warning-missed-warnings-outages",
         "seeds": (0, 1),
         "episodes_per_seed": 10,
         "iterations": 3,
         "episodes_per_iteration": 4,
         "teacher_episodes": 20}
