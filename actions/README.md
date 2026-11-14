# Defender actions

[contracts.py](contracts.py) defines action names, command types, job codes and
feedback codes. [defender_actions.py](defender_actions.py) validates commands,
starts jobs and applies completion effects. Durations are listed in
[action_config.template.toml](action_config.template.toml) and are set by each world folder (see
[world/settings.py](../world/settings.py)).

## Execution

| Command | At start | At completion |
|---|---|---|
| Wait | Accepted; no job | No completion event |
| Inspect | Start job | Save dated/timed compromise finding; clear earlier target warnings |
| Isolate | Start unless already isolated | Set isolation |
| Restore | Immediately isolate and stop service | Clear compromise; restart service only if no outage is active; keep isolation; patch the server if `restore.patches_server` is true; clear target warnings and finding |
| Reconnect | Start unless already connected | Clear isolation |

`restore.patches_server` (true in every world folder for every study) decides whether a finished Restore also
patches its server. A patched server is no longer vulnerable, so spread cannot infect it
again; the next reset makes it vulnerable again. An intrusion from outside still lands on
it, as the starting infection does.

An active scheduled outage keeps the service off even when Restore completes.
Cleanup, patching and evidence retirement still finish normally. The service
restarts when the last covering outage ends, unless another Restore is running.
For example, an outage covering intervals 3–5 keeps the service off when Restore
finishes in interval 3; it can restart in interval 6. Reconnect changes isolation
only and cannot override the outage.

Every active job loses one remaining interval, including its starting interval.
Completion removes the job. An inspection records the truth at completion;
subsequent host changes do not rewrite it. Its timestamp is the upcoming boundary.
Only completed Inspect/Restore retire evidence, for their own defender and target.
Monitoring runs later in the interval, so a later warning remains.

`start_defender_action()` validates before executing. A world transition validates
the entire batch first, then calls `start_validated_defender_action()` without
repeating those checks. This prevents an invalid later command from partially
starting the batch. Both entry paths use the same start rules.

Invalid types raise `TypeError`; invalid IDs, actions or targets raise `ValueError`.
A valid busy command returns `rejected` without replacing the existing job.
An already satisfied Isolate/Reconnect returns `already_satisfied`. Normal
interface calls omit busy defenders. Acceptance never checks hidden compromise.
Standalone action helpers do not advance the shared clock.

`CommandResult` is the immediate submission response. `CommandFeedback` is the
latest full-interval outcome stored in `last_command_feedback` and encoded by
`COMMAND_FEEDBACK_CODES`; completion takes priority, followed by the submission
result, or `none` when neither occurred.

## Action IDs

[defender_action_encoding.py](defender_action_encoding.py) builds an immutable
list of actions, which starts with Wait, then Inspect, Isolate, Restore and Reconnect for each local
server in configured order.

Action IDs identify requested commands. Job codes identify ongoing work, with
0 meaning no job. Feedback codes identify outcomes: none=0, completed=1,
accepted=2, already_satisfied=3, rejected=4.



| Action ID | Defender A command | Defender B command |
|---|---|---|
| 0 | `('wait', None)` | `('wait', None)` |
| 1 | `('inspect', 'A1')` | `('inspect', 'B1')` |
| 2 | `('isolate', 'A1')` | `('isolate', 'B1')` |
| 3 | `('restore', 'A1')` | `('restore', 'B1')` |
| 4 | `('reconnect', 'A1')` | `('reconnect', 'B1')` |
| 5 | `('inspect', 'A2')` | `('inspect', 'B2')` |
| 6 | `('isolate', 'A2')` | `('isolate', 'B2')` |
| 7 | `('restore', 'A2')` | `('restore', 'B2')` |
| 8 | `('reconnect', 'A2')` | `('reconnect', 'B2')` |
| 9 | `('inspect', 'A3')` | `('inspect', 'B3')` |
| 10 | `('isolate', 'A3')` | `('isolate', 'B3')` |
| 11 | `('restore', 'A3')` | `('restore', 'B3')` |
| 12 | `('reconnect', 'A3')` | `('reconnect', 'B3')` |

