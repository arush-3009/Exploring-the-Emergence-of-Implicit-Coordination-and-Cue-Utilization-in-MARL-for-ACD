# Episodes

Plays one episode and saves it (in-memory `EpisodeLog`and saved `EpisodeRecord` for measurements.)

| Module | What it holds |
|---|---|
| [runner.py](runner.py) | `EpisodeRunner(interface, policies).run()` plays one episode and returns an `EpisodeLog`; `Policy`is the callable policy for a defender; `evaluation_seeds(seed, defenders)` is one evaluation seed's sampling seeds and world seed |
| [record.py](record.py) | `EpisodeRecord` is built from a log with `EpisodeRecord.from_log(log, world, episode, evaluation_seed, iteration)`; `relevant_servers`, `available` and `action_labels` are for measurements/stats |
| [record_io.py](record_io.py) | For recording |

The runner asks only the free defenders at every boundary for an action at that observation. 
The log holds each boundary's vectors and the named facts that they were encoded from, each interval's action IDs (`None` while busy) and shared reward, and the world's full
step report for every interval. The report holds hidden truth. The log keeps it for
checking and measuring, and no policy ever receives it.


| Part | What it holds |
|---|---|
| `script` | the episode's random events: the intrusion (server and interval, or none), false warnings, missed servers, outages |
| `intervals[t]` | each defender's action, target, result and completed action, and the target's state when a targeted action started; the reward and its parts; every request with its outcome; every server's hidden state at the end of the interval; the intrusion, the outages started, the spread attempts started and resolved, and the warnings delivered in the interval |
| `boundaries[b]` | each defender's observation at boundary `b` |
| `initial_servers`, `total_reward` | the hidden state at boundary 0 and the sum of the shared rewards |

`records.jsonl.gz` holds one JSON line per episode, in order.
