# reliable warnings

One world of Study 1, the receiver, does B use A's interruptions?. Every team, baseline and control is scored on the same 2000 episodes; the trained teams and the controls choose greedily and the rule baselines follow their rules. One team is one pair of defenders A and B trained for one seed. A mean is over the teams that have a value, with their number; a value with nothing to count is shown as undefined, never as zero.

## Teams and baselines

|  | team reward per episode | B's infected server-intervals per intrusion episode | intrusion episodes ending with an infected B server | B's first action on the attacked pair's server came with no warning and no infected finding of its own visible, server monitored | B inspected, isolated or restored a running, connected server right after its request to the partner failed |
|---|---|---|---|---|---|
| cue-visible, seed 0 | -38.43 | 7.063 | 0.0% | 82.0% | 100.0% |
| cue-visible, seed 1 | -35.99 | 7.051 | 0.0% | 83.1% | 100.0% |
| cue-visible, seed 2 | -35.99 | 7.051 | 0.0% | 83.1% | 100.0% |
| cue-visible, seed 3 | -42.25 | 9.222 | 0.0% | 31.7% | 44.5% |
| cue-visible, seed 4 | -40.5 | 8.724 | 0.0% | 48.7% | 49.9% |
| **cue-visible, mean** | **-38.63** (5 teams) | **7.822** (5 teams) | **0.0%** (5 teams) | **65.7%** (5 teams) | **78.9%** (5 teams) |
| cue-hidden-unknown, seed 0 | -44.6 | 10.12 | 0.0% | 0.0% | undefined |
| cue-hidden-unknown, seed 1 | -47.53 | 11.48 | 0.0% | 0.0% | undefined |
| cue-hidden-unknown, seed 2 | -53.96 | 18 | 33.4% | 0.0% | undefined |
| cue-hidden-unknown, seed 3 | -43.96 | 10.15 | 0.0% | 0.0% | undefined |
| cue-hidden-unknown, seed 4 | -45.22 | 10.12 | 0.0% | 0.0% | undefined |
| **cue-hidden-unknown, mean** | **-47.05** (5 teams) | **11.98** (5 teams) | **6.7%** (5 teams) | **0.0%** (5 teams) | **undefined** (0 teams) |
| always wait | -112.5 | 34.64 | 100.0% | 0.0% | undefined |
| inspect-first teacher | -49.51 | 11.48 | 0.0% | 0.0% | 40.9% |
| restore-on-warning teacher | -42.19 | 9.482 | 0.0% | 0.0% | 17.5% |
| uniform random | -475.5 | 10.65 | 14.3% | 68.3% | 28.8% |

Every measurement of every team, baseline and control, with its numerator and denominator, is in [world_table.csv](world_table.csv). Each arm's five teams with their mean, standard deviation, minimum and maximum are in `training-arms/<arm>/arm_summary.csv`. The study's measurements.csv defines every measurement.

## Figures

### How well does each team defend?

![How well does each team defend?](figures/W1-performance.png)

The points drawn are in [figures/W1-performance.csv](figures/W1-performance.csv), the vector version in [figures/W1-performance.svg](figures/W1-performance.svg).

### Does B act on its partner's request failures?

![Does B act on its partner's request failures?](figures/W2-behaviour.png)

The points drawn are in [figures/W2-behaviour.csv](figures/W2-behaviour.csv), the vector version in [figures/W2-behaviour.svg](figures/W2-behaviour.svg).

### What does each cue-visible team lose when the cue is removed at evaluation?

![What does each cue-visible team lose when the cue is removed at evaluation?](figures/W3-controls.png)

The points drawn are in [figures/W3-controls.csv](figures/W3-controls.csv), the vector version in [figures/W3-controls.svg](figures/W3-controls.svg).

### How did training go in each arm?

![How did training go in each arm?](figures/W4-learning.png)

The points drawn are in [figures/W4-learning.csv](figures/W4-learning.csv), the vector version in [figures/W4-learning.svg](figures/W4-learning.svg).

## Example episodes

No episode has been chosen yet.
