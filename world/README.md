# World

[environment.py](environment.py) holds the world. `WorldEnvironment` keeps one `WorldState`
and the six settings dictionaries of a world folder, and steps the world one interval at a
time. [environment_interface.py](environment_interface.py) wraps it for the episode runner.
It takes each free defender's action ID, advances the world once and returns each defender's
encoded observation, who is free next, the shared reward, whether the episode is over, and the
full step report for the record.

| Module | What it holds |
|---|---|
| [state.py](state.py) | the server, job and evidence records, and the starting state |
| [settings.py](settings.py) | loads a world folder's six settings files, applies overrides and validates everything |
| [world_config.py](world_config.py), [layout.py](layout.py) | the layout, zones, pairs and server order |
| [episode_script.py](episode_script.py) | draws each episode's random events and applies outages |
| [results.py](results.py) | the shapes of the step report and the boundary result |
| [config_io.py](config_io.py) | TOML reading |

## One interval

`step(commands)` plays interval t, from boundary S_t to S_(t+1), in this order.

1. Check the commands. Every free defender must send one.
2. Apply the episode's intrusion if this is its interval, then start and end the outages that are due.
3. Start the attacks that can start, judged by the state at S_t.
4. Start the defenders' commands. Restore isolates and stops its server right away.
5. Count down the defenders' jobs and apply the ones that complete.
6. Count down the attacks and resolve the ones that are due.
7. Run the interval's requests.
8. Run monitoring and deliver the warnings that are due, marked as received at t+1.
9. Store each defender's feedback on its command.
10. Score the interval and move the clock to t+1.

Every world folder has 50 intervals, so the boundaries run from S0 to S50.
The step report is a plain dictionary with everything that happened in the interval,
including the hidden truth about infections. The episode runner keeps one per interval in the
record.

## Outages

An outage keeps a server's service off from its start interval for its duration, irrespective of what the server's defender does to the server meanwhile. A Restore that completes inside an outage still cleans
and patches the server. The service comes back when the outage ends, as long as no other
outage covers the server and no Restore is still running on it.
