# Worlds

The five worlds every study has, with each world being one folder each with the six settings files of the
simulator, `world_config.toml`, `action_config.toml`, `attacker_config.toml`,
`workload_config.toml`, `observation_config.toml` and `reward_config.toml`.

The five worlds differ only in how reliable the warnings are and whether outages happen.

| World | False warnings per episode | Chance a server's warnings are missed | Outages per episode |
|---|---:|---:|---:|
| `reliable-warnings` | 0 | 0 | 0 |
| `one-false-warning` | 1 | 0 | 0 |
| `two-false-warnings` | 2 | 0 | 0 |
| `one-false-warning-missed-warnings` | 1 | 0.2 | 0 |
| `one-false-warning-missed-warnings-outages` | 1 | 0.2 | 1, lasting 3 intervals |

Everything else is the same in all five. Each has six servers in three cross-zone pairs, 50
intervals, a random intrusion into one server at a random interval in 80 percent of
episodes, A's early warning at age 2 and the ordinary warning at age 6, a cost of 2 per
infected server per interval, 1 per failed request and 0.5 per inspection, and a Restore that
also patches its server.
