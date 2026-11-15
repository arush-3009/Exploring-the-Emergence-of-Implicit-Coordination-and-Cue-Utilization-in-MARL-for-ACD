# one false warning missed warnings

One world of Study 4, A from the teacher next to a fixed B. Every team, baseline and control is scored on the same 2000 episodes; the trained teams and the controls choose greedily and the rule baselines follow their rules. One team is one pair of defenders A and B trained for one seed. A mean is over the teams that have a value, with their number; a value with nothing to count is shown as undefined, never as zero.

## Teams and baselines

|  | team reward per episode | B's infected server-intervals per intrusion episode | intrusion episodes ending with an infected B server | A interrupted the attacked pair's server after the intrusion | B responded to A's interruption |
|---|---|---|---|---|---|
| cue-visible, seed 0, under 1 percent interruptions of the attacked pair's server | -34.93 | 15.77 | 18.5% | 0.0% | undefined |
| cue-visible, seed 1 | -34.99 | 11.21 | 6.4% | 55.5% | 99.7% |
| cue-visible, seed 2, under 1 percent interruptions of the attacked pair's server | -38.16 | 14.61 | 16.0% | 0.0% | undefined |
| cue-visible, seed 3 | -35.8 | 12.24 | 10.8% | 87.9% | 99.9% |
| cue-visible, seed 4 | -37.62 | 11.93 | 6.5% | 50.0% | 99.4% |
| **cue-visible, mean** | **-36.3** (5 teams) | **13.15** (5 teams) | **11.6%** (5 teams) | **38.7%** (5 teams) | **99.7%** (3 teams) |
| cue-hidden-failures-suppressed, seed 0, under 1 percent interruptions of the attacked pair's server | -35.5 | 15.77 | 18.5% | 0.0% | undefined |
| cue-hidden-failures-suppressed, seed 1, under 1 percent interruptions of the attacked pair's server | -38.29 | 14.83 | 15.2% | 0.0% | undefined |
| cue-hidden-failures-suppressed, seed 2 | -51.35 | 14.61 | 16.0% | 2.3% | 2.2% |
| cue-hidden-failures-suppressed, seed 3 | -53.96 | 31.65 | 85.8% | 1.2% | 0.0% |
| cue-hidden-failures-suppressed, seed 4, under 1 percent interruptions of the attacked pair's server | -40.09 | 14.99 | 15.8% | 0.0% | undefined |
| **cue-hidden-failures-suppressed, mean** | **-43.84** (5 teams) | **18.37** (5 teams) | **30.3%** (5 teams) | **0.70%** (5 teams) | **1.1%** (2 teams) |
| always wait | -56.3 | 34.64 | 100.0% | 0.0% | undefined |
| inspect-first teacher | -41.65 | 15.72 | 18.3% | 83.8% | 40.4% |
| restore-on-warning teacher | -47.76 | 13.77 | 17.8% | 80.3% | 1.7% |
| uniform random | -458.9 | 10.65 | 14.3% | 71.4% | 19.8% |
| A always waits next to the fixed B, seed 0 | -34.16 | 15.77 | 18.5% | 0.0% | undefined |
| A always waits next to the fixed B, seed 1 | -35.32 | 14.83 | 15.2% | 0.0% | undefined |
| A always waits next to the fixed B, seed 2 | -37.87 | 14.61 | 16.0% | 0.0% | undefined |
| A always waits next to the fixed B, seed 3 | -53.59 | 31.89 | 86.3% | 0.0% | undefined |
| A always waits next to the fixed B, seed 4 | -38.23 | 14.99 | 15.8% | 0.0% | undefined |

Every measurement of every team, baseline and control, with its numerator and denominator, is in [world_table.csv](world_table.csv). Each arm's five teams with their mean, standard deviation, minimum and maximum are in `training-arms/<arm>/arm_summary.csv`. The study's measurements.csv defines every measurement.

## Figures

### How well does each team defend?

![How well does each team defend?](figures/W1-performance.png)

The points drawn are in [figures/W1-performance.csv](figures/W1-performance.csv), the vector version in [figures/W1-performance.svg](figures/W1-performance.svg).

### Does A interrupt its servers in ways B can see, and does B respond?

![Does A interrupt its servers in ways B can see, and does B respond?](figures/W2-signalling.png)

The points drawn are in [figures/W2-signalling.csv](figures/W2-signalling.csv), the vector version in [figures/W2-signalling.svg](figures/W2-signalling.svg).

### What does each cue-visible team lose when the cue is removed at evaluation?

![What does each cue-visible team lose when the cue is removed at evaluation?](figures/W3-controls.png)

The points drawn are in [figures/W3-controls.csv](figures/W3-controls.csv), the vector version in [figures/W3-controls.svg](figures/W3-controls.svg).

### How did training go in each arm?

![How did training go in each arm?](figures/W4-learning.png)

The points drawn are in [figures/W4-learning.csv](figures/W4-learning.csv), the vector version in [figures/W4-learning.svg](figures/W4-learning.svg).

### Given the same inputs, how likely is each A to interrupt?

![Given the same inputs, how likely is each A to interrupt?](figures/W5-probe.png)

The points drawn are in [figures/W5-probe.csv](figures/W5-probe.csv), the vector version in [figures/W5-probe.svg](figures/W5-probe.svg).

## Example episodes

No episode has been chosen yet.
