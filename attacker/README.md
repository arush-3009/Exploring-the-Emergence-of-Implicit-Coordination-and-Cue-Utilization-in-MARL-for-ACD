# Scripted attacker

[scripted_attacker.py](scripted_attacker.py) starts and advances directed attempts
between paired servers. The attack duration is listed in
[attacker_config.template.toml](attacker_config.template.toml) and set by each world folder.

`start_attack_jobs()` preserves existing attempts and creates eligible new ones
before defender starting effects. `advance_attack_jobs()` decrements each timer
once, including its starting interval, and resolves due attempts after defender
completion.

Eligibility at start and success at completion require:

- A compromised, connected source.
- A clean, connected target with a running, vulnerable file service.

The source does not need a running file service or continued vulnerability.
A server patched by a Restore is not vulnerable for the rest of the episode.


The attacker reads hidden truth; that information is excluded from defender
observations. This deterministic paired model has no discovery or learned attacker.

## Random intrusions

[intrusion.py](intrusion.py) brings an infection from outside when the world has an
optional `[intrusion]` table.

| Setting | Meaning |
|---|---|
| `servers` | Servers the intrusion can hit, each equally likely |
| `start_interval_range` | First and last interval it can start in |
| `clean_episode_share` | Share of episodes with no intrusion |

At each reset, `randomly_draw_intrusion(settings, generator)` draws the episode's
intrusion, or `None` for a clean episode. At the start of each interval, before attacks start,
`apply_due_intrusion(state)` infects the intrusion's server if its interval has come and
records the infection as starting at that interval's left boundary. Spread from it can
start in the same interval and warnings arrive after the usual delays. A server that is
already infected keeps its earlier infection start. The intrusion lands whatever the
server's condition, as the starting infection does. The world step report names the
server in that interval's `intrusion` entry.

`WorldEnvironment` holds the generator as the world's random-number generator.
`set_world_rng(seed)` makes it from the seed, and the next reset draws the first intrusion
of the new sequence. `world_seed` is that
seed, or `None` for a world with nothing random in it. The trainer seeds it from its run seed, unless the training job then
sets a seed of its own, as the sender studies' training does, and each evaluation seeds it
from its evaluation seed. The draws use Python's `random`, so the same seed gives the same intrusions on every machine.


