# Exploring Implicit Coordination Through Signalling and Cue-Utilization in Multi-Agent RL for Autonomous Cyber Defence

Two RL cyber-defender agents guard a small simulated enterprise network. Each is responsible for one zone of the enterprise network, and there exists no message channel between them. The only thing that crosses from one zone to the other is a side effect. When agent-A restores a compromised server, that server's connection to its partner in zone-B goes down, and agent-B can see it (from zone-B's side). The project then essentially tries to focus on two things, the first being whether agent-B learns to treat that disrupted connection as an early warning of a compromise in its zone (as agent-A would break a connection to restore its server if it suspects the server to be compromised, and because this server is connected to one in zone-B, the intrusion could have moved laterally to zone-B as well), and the second being whether agent-A comes to cause it specifically because of how agent-B reacts to it. The first makes the disruption a cue, the second would make it a signal.

A blog post with a deep-dive into its major findings and what they mean can be found [here](https://arush.cc/thoughts/talking-between-the-lines). This repository holds the simulator, the training code, the five studies, every result table and figure, and the trained weights of 250 teams (where a team is the 2 agents playing together).

## Findings

- Agent-B learned to read the disruption. In 24 of 25 pairs of teams, the team whose agent-B could see the disruption as a cue earned more reward than the team whose agent-B could not, by 7.6 per episode on average, in all five worlds. Teams that had learned with it lost about twice that when it was hidden from them at evaluation, showing that they did, in fact, come to depend on using the disrupted connection as a hint.
- Agent-A retained (instead of invented) the behaviour of interrupting a connection to send a signal, but only beside an agent-B that could see the disruption and knew how to react well to make use of it, and only where agent-A was already doing so when training began. When starting from random weights, or beside an agent-B that was still learning, agent-A gave the behaviour up.
- With routine, ordinary outages added to the world, agent-A gave it up even beside an agent-B that could see the disruption and knew how to make use of it. 
- Hence, it can be fairly concluded that cue-utilization by the receiver emerged in every world whereas signalling by the sender was mostly retained/held onto instead of emerging from scratch.

## Environment

Each zone has three file servers, an employee's computer and one defender-agent, and an intruder lands on a random server in 80% of episodes and spreads to its partner across the zones. A defender sees only its own zone, and can wait, inspect, isolate, restore or reconnect its own servers. Both defender-agents share the same reward at the end of every interval. Both are small feed-forward neural networks trained with independent PPO after behaviour cloning on a simple rule. Study 1 asks the receiver question. Studies 2 to 5 ask the sender question, with a compromised server in zone-A costing nothing so that agent-A has no reason of its own to restore one. Every study runs in five worlds, which vary how reliable the warnings are and whether outages happen, with five seeds each.

## Repo Structure

| Folder | What it holds |
|---|---|
| `world/`, `attacker/`, `workload/`, `actions/`, `observations/`, `rewards/` |  Simulator |
| `policies/` | hand-written heuristics, neural policy, and baselines |
| `learning/` | Behaviour cloning & IPPO trainer |
| `episodes/`, `measurements/`, `figures/` | Playing & recording an episode and measurements & figures |
| `studies/` | 5 studies along with the launcher(s) to run everything |
| `worlds/` |  Settings of the 5 worlds |
| `experiment-runs/` | Results & recorded run data |
| `checks/` | Code tests |
| `tools/timeline.py` | Writes one evaluation episode as an HTML page |

## Reproducing the Results & Runs

Use Python 3.12 with [uv](https://docs.astral.sh/uv/).


Everything runs on the CPU; on Linux, torch is pulled from the CPU-only index named in `pyproject.toml`.

```
uv sync
uv run --locked python -m pytest -q
uv run --locked python -m studies.launch --all --check
```

The last line validates the settings and the job graph and launches nothing. It also prints how many jobs the full run would be.

A tiny run first (smoke runs) can be used to see the whole pipeline go through in minutes. `--smoke` uses one world and two seeds while `--full-smoke` uses every world and seed. Results are produced under `runs/smoke/` or `runs/full-smoke/` so nothing of the real results is touched.

```
uv run --locked python -m studies.launch --all --smoke
```

For the complete, actual run

```
uv run --locked python -m studies.launch --all --jobs 32
```

That trains 250 teams (5 studies, 5 worlds, 5 seeds, two versions of each team) for 3,000 iterations of 16 episodes each, evaluates every team, baseline and control on 2,000 episodes, and then measures and draws the figures and graphs. It took about 11 hours on a 16-core machine. `--study 1` runs one study; studies 3 to 5 need study 1's weights, and the launcher takes care of the order. Logs go to `runs/logs/`.

Results for the main, complete run are produced in 2 folders. `runs/` is private and ignored by git, and holds the full episode records, the markers of finished jobs and the logs. `experiment-runs/` is what the repository tracks. To recompute the tables, figures and experiment READMEs from the saved records without training anything, run

```
uv run --locked python -m studies.launch --all --only measure,draw --jobs 8
```

Every team folder under `experiment-runs/` has a `run.json` that names the commit the code was at. The launcher refuses to start with uncommitted changes, so every `run.json` always names one clean commit.
