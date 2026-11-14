# Policies

A policy takes its defender's encoded observation vector and returns one action ID. Only free defenders choose actions. Every policy also has `describe()`, which returns its
type and, if it has one, its seed, for recording and replaying. Only NeuralPolicy uses neural networks and is the one that gets trained. InspectThenRestore is used as the teacher for warm-starts.

| Policy | What it does |
|---|---|
| [AlwaysWait](always_wait.py) | Waits at every decision. Wait is action ID 0 for every defender. |
| [RandomPolicy](random_policy.py) | Picks uniformly over all action IDs, with its own seeded generator. |
| [InspectThenRestore](inspect_then_restore.py) | Inspects a server when its warning arrives, restores it if the finding says infected, reconnects it when the restore finishes. |
| [RestoreReconnectOnlyWhenHelpful](restore_reconnect_only_when_helpful.py) | Restores a server as soon as its warning arrives, reconnects it when the restore finishes. |
| [NeuralPolicy](neural_policy.py) | Uses an actor neural network. Feeds a defender's observation vector into the actor to get probabilities for 13 action choices. |

Both, InspectThenRestore and RestoreReconnectOnlyWhenHelpful, read only their own defender's open warnings and
findings (and not the status of a server's connection to its peer in the other zone). At each free decision they first reconnect an isolated server whose service is
running. InspectThenRestore then restores a server with an infected finding, otherwise
inspects a server with an open warning. RestoreReconnectOnlyWhenHelpful restores a server with an open
warning straight away. With nothing to do, both wait. Ties go in configured server order. On a
false warning InspectThenRestore pays one inspection and moves on, while RestoreReconnectOnlyWhenHelpful
restores a clean server. The studies' warm start copies InspectThenRestore.

NeuralPolicy holds the weights a team starts with or ends with. `mode="sample"` draws from the
softmax with the policy's own seeded generator, which is how training plays. `mode="greedy"`
always takes the highest score, which is how every evaluation plays.