# one false warning missed warnings outages

One world of Study 2, both defenders from the teacher, both learning. Every team, baseline and control is scored on the same 2000 episodes; the trained teams and the controls choose greedily and the rule baselines follow their rules. One team is one pair of defenders A and B trained for one seed. A mean is over the teams that have a value, with their number; a value with nothing to count is shown as undefined, never as zero.

## Teams and baselines

|  | team reward per episode | B's infected server-intervals per intrusion episode | intrusion episodes ending with an infected B server | A interrupted the attacked pair's server after the intrusion | B responded to A's interruption |
|---|---|---|---|---|---|
| cue-visible, seed 0, under 1 percent interruptions of the attacked pair's server | -43.36 | 15.53 | 18.8% | 0.0% | undefined |
| cue-visible, seed 1, under 1 percent interruptions of the attacked pair's server | -45.4 | 15.46 | 18.0% | 0.0% | undefined |
| cue-visible, seed 2, under 1 percent interruptions of the attacked pair's server | -45.17 | 14.68 | 15.2% | 0.0% | undefined |
| cue-visible, seed 3, under 1 percent interruptions of the attacked pair's server | -45.2 | 15.21 | 18.0% | 0.0% | undefined |
| cue-visible, seed 4, under 1 percent interruptions of the attacked pair's server | -44.85 | 15.36 | 17.2% | 0.0% | undefined |
| **cue-visible, mean** | **-44.8** (5 teams) | **15.25** (5 teams) | **17.5%** (5 teams) | **0.0%** (5 teams) | **undefined** (0 teams) |
| cue-hidden-failures-suppressed, seed 0, under 1 percent interruptions of the attacked pair's server | -46.77 | 14.51 | 16.1% | 0.0% | undefined |
| cue-hidden-failures-suppressed, seed 1, under 1 percent interruptions of the attacked pair's server | -46.95 | 14.87 | 15.4% | 0.0% | undefined |
| cue-hidden-failures-suppressed, seed 2, under 1 percent interruptions of the attacked pair's server | -43.61 | 15.37 | 18.2% | 0.0% | undefined |
| cue-hidden-failures-suppressed, seed 3, under 1 percent interruptions of the attacked pair's server | -44.81 | 15.24 | 17.2% | 0.0% | undefined |
| cue-hidden-failures-suppressed, seed 4, under 1 percent interruptions of the attacked pair's server | -43.82 | 15.38 | 17.8% | 0.0% | undefined |
| **cue-hidden-failures-suppressed, mean** | **-45.19** (5 teams) | **15.08** (5 teams) | **16.9%** (5 teams) | **0.0%** (5 teams) | **undefined** (0 teams) |
| always wait | -65.28 | 34.63 | 100.0% | 0.0% | undefined |
| inspect-first teacher | -50.31 | 15.7 | 18.3% | 83.0% | 39.9% |
| restore-on-warning teacher | -56.22 | 13.73 | 17.7% | 79.6% | 1.8% |
| uniform random | -461 | 10.65 | 14.3% | 71.2% | 19.8% |

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
