# Local observations and monitoring

| Module | Responsibility |
|---|---|
| [monitoring.py](monitoring.py) | Deliver delayed local evidence during a transition |
| [defender_observation.py](defender_observation.py) | Read permitted facts at a completed boundary |
| [contracts.py](contracts.py) | Named observation fields and numeric vector type |
| [schema.py](schema.py) | Ordered fields, categories, scales and feature names |
| [defender_observation_encoding.py](defender_observation_encoding.py) | Validate values and encode the shared schema |

## Evidence timing

During interval t, from S_t to S_(t+1), the clock remains t until the world makes
its final increment. Monitoring runs after workload and marks new warnings as having been received at t+1.

Each detector fires once per infection at its exact delay. Basic monitoring
applies to every zone; extra monitoring applies to configured zones and has its own delay. 
Cleanup removes infection timing. Completed Inspect clears earlier warnings for its target; completed Restore
clears both warnings and findings. Monitoring runs afterward, so a new delivery
in that same interval stays open. Unfinished jobs clear nothing. 




| Setting | Current value |
|---|---|
| `monitoring.basic_delay_steps` | 6 transitions |
| `monitoring.extra_information_delay_steps` | 2 transitions |
| `monitoring.extra_detector_zones` | A |



## Named observation

`env.observe(defender_id)` returns for every defender agent fresh dictionaries with six general/own-status fields
and eight fields per local server.

Missing evidence uses -1.


| Scope | Field | Meaning |
|---|---|---|
| Own status | `elapsed_steps` | Completed boundary index k; ages below use k, not k+1. |
| Own status | `extra_detector_available` | 0 absent; 1 present in this defender's zone. |
| Own status | `job_action` | 0 no active job; 1 inspect; 2 isolate; 3 restore; 4 reconnect |
| Own status | `job_target` | 0 none; otherwise one-based configured local server index. |
| Own status | `job_remaining_steps` | Remaining intervals; 0 when free. |
| Own status | `last_command_feedback` | 0 none; 1 completed; 2 accepted; 3 already_satisfied; 4 rejected |
| Each local server | `service_running` | 0 stopped; 1 running locally. |
| Each local server | `isolated` | 0 connected; 1 isolated locally. |
| Each local server | `employee_request_result` | Latest employee-to-this-server work: -1 absent; 0 failed; 1 succeeded. |
| Each local server | `peer_request_result` | Latest this-server-to-peer work: -1 absent; 0 failed; 1 succeeded. |
| Each local server | `warning_received` | 0 no outstanding warning; 1 warning still awaiting handling. |
| Each local server | `warning_age` | -1 absent; otherwise k minus received_step. |
| Each local server | `inspection_finding` | -1 absent; 0 clean at inspection; 1 compromised at inspection. |
| Each local server | `inspection_age` | -1 absent; otherwise k minus completed_step. |




## Numeric encoding

`env.encode_observation(defender_id)` reads one named observation and passes it
to a prepared `ObservationEncoder`. It returns a one-dimensional float32 array in configured local server order.


Categories become one-hot indicators, including unknown work/inspection results.
Flags remain 0/1. Time and evidence ages use the configured horizon as divisor;
remaining job steps use the maximum defender duration. Missing ages stay -1.
Validation rejects invalid types, categories, flags, counters and server sets.




| Index | Feature | A at reset |
|---|---|---|
| 0 | `elapsed_fraction` | 0 |
| 1 | `extra_detector_available` | 1 |
| 2 | `job_action.no_job` | 1 |
| 3 | `job_action.inspect` | 0 |
| 4 | `job_action.isolate` | 0 |
| 5 | `job_action.restore` | 0 |
| 6 | `job_action.reconnect` | 0 |
| 7 | `job_target.none` | 1 |
| 8 | `job_target.server_1` | 0 |
| 9 | `job_target.server_2` | 0 |
| 10 | `job_target.server_3` | 0 |
| 11 | `job_remaining_fraction` | 0 |
| 12 | `last_command_feedback.none` | 1 |
| 13 | `last_command_feedback.completed` | 0 |
| 14 | `last_command_feedback.accepted` | 0 |
| 15 | `last_command_feedback.already_satisfied` | 0 |
| 16 | `last_command_feedback.rejected` | 0 |
| 17 | `server_1.service_running` | 1 |
| 18 | `server_1.isolated` | 0 |
| 19 | `server_1.employee_request_result.unknown` | 1 |
| 20 | `server_1.employee_request_result.failed` | 0 |
| 21 | `server_1.employee_request_result.succeeded` | 0 |
| 22 | `server_1.peer_request_result.unknown` | 1 |
| 23 | `server_1.peer_request_result.failed` | 0 |
| 24 | `server_1.peer_request_result.succeeded` | 0 |
| 25 | `server_1.warning_received` | 0 |
| 26 | `server_1.warning_age_fraction` | -1 |
| 27 | `server_1.inspection_finding.unknown` | 1 |
| 28 | `server_1.inspection_finding.clean` | 0 |
| 29 | `server_1.inspection_finding.compromised` | 0 |
| 30 | `server_1.inspection_age_fraction` | -1 |
| 31 | `server_2.service_running` | 1 |
| 32 | `server_2.isolated` | 0 |
| 33 | `server_2.employee_request_result.unknown` | 1 |
| 34 | `server_2.employee_request_result.failed` | 0 |
| 35 | `server_2.employee_request_result.succeeded` | 0 |
| 36 | `server_2.peer_request_result.unknown` | 1 |
| 37 | `server_2.peer_request_result.failed` | 0 |
| 38 | `server_2.peer_request_result.succeeded` | 0 |
| 39 | `server_2.warning_received` | 0 |
| 40 | `server_2.warning_age_fraction` | -1 |
| 41 | `server_2.inspection_finding.unknown` | 1 |
| 42 | `server_2.inspection_finding.clean` | 0 |
| 43 | `server_2.inspection_finding.compromised` | 0 |
| 44 | `server_2.inspection_age_fraction` | -1 |
| 45 | `server_3.service_running` | 1 |
| 46 | `server_3.isolated` | 0 |
| 47 | `server_3.employee_request_result.unknown` | 1 |
| 48 | `server_3.employee_request_result.failed` | 0 |
| 49 | `server_3.employee_request_result.succeeded` | 0 |
| 50 | `server_3.peer_request_result.unknown` | 1 |
| 51 | `server_3.peer_request_result.failed` | 0 |
| 52 | `server_3.peer_request_result.succeeded` | 0 |
| 53 | `server_3.warning_received` | 0 |
| 54 | `server_3.warning_age_fraction` | -1 |
| 55 | `server_3.inspection_finding.unknown` | 1 |
| 56 | `server_3.inspection_finding.clean` | 0 |
| 57 | `server_3.inspection_finding.compromised` | 0 |
| 58 | `server_3.inspection_age_fraction` | -1 |
