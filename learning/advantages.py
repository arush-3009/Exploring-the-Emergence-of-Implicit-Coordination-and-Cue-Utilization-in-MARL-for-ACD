import numpy as np


def advantages_and_returns(shared_rewards: list[float],
                           decision_intervals: np.ndarray,
                           values: np.ndarray, #array of critic's predicted value (i.e. estimated return) of a given observation, for all observations where the defender took a decision in this episode.
                           gamma: float,
                           gae_lambda: float,) -> tuple[np.ndarray, np.ndarray]:
    
    #decision_intervals in an array which gives the interval-indices (so, 0-49) where a decision was taken/started.
    end_intervals = [*decision_intervals[1:], len(shared_rewards)]
    
    advantages = np.zeros(len(values))
    
    next_value = 0.0
    next_advantage = 0.0


    for i in reversed(range(len(values))):
        
        start_interval = decision_intervals[i]
        
        k = end_intervals[i] - start_interval
        
        decision_intervals_rewards_discounted = []
        for j in range(k):
            decision_intervals_rewards_discounted.append( (gamma**j) * (shared_rewards[start_interval + j]) )
    
        decision_reward = sum(decision_intervals_rewards_discounted)
        
        # δ → one decision-step TD error. For decisions spanning multiple intervals, 
        # δ takes the discounted sum of rewards across all intervals spanning the single 
        # decision and uses the critic's predicted value of the observation of the interval 
        # where the next decision is taken.
        delta = ( (decision_reward) + (gamma**k) * next_value ) - values[i]
        
        #backward computation of advantages of the decisions across an episode.
        advantages[i] = delta + ( gamma**k * gae_lambda * next_advantage )
        
        
        next_value = values[i]
        next_advantage = advantages[i]

    return advantages, advantages + values
