from dataclasses import dataclass

import numpy as np

from episodes.runner import EpisodeLog


@dataclass
class DefenderDecisions:

    observations: np.ndarray  # what the defender saw when it chose
    action_ids: np.ndarray  # the action ID it chose
    intervals: np.ndarray  # the interval at which it chose


def defender_decisions(log: EpisodeLog, defender_id: str) -> DefenderDecisions:
    
    intervals = [t for t, chosen in enumerate(log.action_ids) if chosen[defender_id] is not None]
    
    return DefenderDecisions(
        observations=np.stack([log.observations[t][defender_id] for t in intervals]),
        action_ids=np.array([log.action_ids[t][defender_id] for t in intervals]),
        intervals=np.array(intervals),
    )
