# Shared reward

[shared_reward.py](shared_reward.py) scores each interval once the actions, the connection-requests between peers in different zones and warning-monitoring have run. Both defenders share the same score.

```text
compromise_cost      = negative reward due to compromised servers in every interval

request_failure_cost = negative reward due to failed connection requests between peers in different zones and between the employee computer and the servers in every interval

inspection_cost      = negative reward for inspection effort

shared_reward        = total common reward shared by both defenders
```

Every world folder uses 2.0 per infected server per interval, 1.0 per failed request and 0.5
per inspection. Infection is counted from the true state at the end of the interval, after
that interval's restores have completed. The
episode's total reward is the plain sum over its 50 intervals.

## Zone weights

A zone can get its own infection weight through `[compromise_penalties_by_zone]`. The four
sender studies set A's weight to 0 through an override on the world folder, so A's own
infected servers cost the team nothing. A's infections still spread to B and still raise
warnings, and A still gets a negative reward for its inspections and for the connection-requests its actions fail. Study 1
uses the ordinary weight in both zones.

```toml
[compromise_penalties_by_zone]
A = 0.0
```
