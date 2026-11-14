# Figures

Draws the figures of `experiment-runs/` from measurement. A team is one pair of defenders, i.e. defender A and defender B corresponding to a single seed in one arm (i.e. either cue-visible arm or cue-hidden arm) in one world of a study.


| Figure | Intuition | Reads |
|---|---|---|
| W1 | How well each team defends.| `world_table.csv`, each arm's `arm_summary.csv` |
| W2 | Does B act on its partner's request failures? (receiver) Does A interrupt its servers in ways B can see, and does B respond? (sender) |  same |
| W3 | What each cue-visible team loses when the cue is removed at evaluation. |  same |
| W4 | Training in each arm |  same, each arm's `learning_curve.csv` and, in the sender studies, `training_behaviour.csv` |
| W5 | On the same inputs, how likely is each A to interrupt? (sender) | `world_table.csv`, each arm's `arm_summary.csv` |
| S1 to S4 | The same questions for the entire study with all worlds compared. | the five world tables and their arm summaries |
| cross-study | How many teams A interrupts the attacked-pair's server in at least 1 percent of intrusion episodes. | `sender-studies-summary.csv` |

One dot is one team.
