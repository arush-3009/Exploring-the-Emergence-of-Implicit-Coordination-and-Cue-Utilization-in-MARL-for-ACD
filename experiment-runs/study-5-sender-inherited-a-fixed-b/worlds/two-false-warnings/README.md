# two false warnings

One world of Study 5, A inherited from study 1 next to a fixed B. Every team, baseline and control is scored on the same 2000 episodes; the trained teams and the controls choose greedily and the rule baselines follow their rules. One team is one pair of defenders A and B trained for one seed. A mean is over the teams that have a value, with their number; a value with nothing to count is shown as undefined, never as zero.

## Teams and baselines

|  | team reward per episode | B's infected server-intervals per intrusion episode | intrusion episodes ending with an infected B server | A interrupted the attacked pair's server after the intrusion | B responded to A's interruption |
|---|---|---|---|---|---|
| cue-visible, seed 0 | -31.22 | 9.075 | 0.0% | 100.0% | 100.0% |
| cue-visible, seed 1 | -32.11 | 10.69 | 7.3% | 33.4% | 99.6% |
| cue-visible, seed 2 | -31.1 | 9.7 | 2.6% | 67.7% | 100.0% |
| cue-visible, seed 3 | -34.33 | 11.1 | 1.9% | 99.2% | 95.6% |
| cue-visible, seed 4, under 1 percent interruptions of the attacked pair's server | -40.04 | 21.05 | 45.1% | 0.0% | undefined |
| **cue-visible, mean** | **-33.76** (5 teams) | **12.32** (5 teams) | **11.4%** (5 teams) | **60.0%** (5 teams) | **98.8%** (4 teams) |
| cue-hidden-failures-suppressed, seed 0, under 1 percent interruptions of the attacked pair's server | -56.16 | 34.4 | 99.3% | 0.0% | undefined |
| cue-hidden-failures-suppressed, seed 1, under 1 percent interruptions of the attacked pair's server | -41.42 | 19.37 | 40.2% | 0.55% | 0.0% |
| cue-hidden-failures-suppressed, seed 2, under 1 percent interruptions of the attacked pair's server | -46.21 | 23.77 | 54.3% | 0.49% | 0.0% |
| cue-hidden-failures-suppressed, seed 3, under 1 percent interruptions of the attacked pair's server | -56.7 | 34.64 | 100.0% | 0.0% | undefined |
| cue-hidden-failures-suppressed, seed 4, under 1 percent interruptions of the attacked pair's server | -40.94 | 21.05 | 45.1% | 0.0% | undefined |
| **cue-hidden-failures-suppressed, mean** | **-48.29** (5 teams) | **26.65** (5 teams) | **67.8%** (5 teams) | **0.21%** (5 teams) | **0.0%** (2 teams) |
| always wait | -56.3 | 34.64 | 100.0% | 0.0% | undefined |
| inspect-first teacher | -37.74 | 11.28 | 0.0% | 99.7% | 51.5% |
| restore-on-warning teacher | -52.73 | 8.785 | 0.0% | 92.4% | 2.8% |
| uniform random | -458.9 | 10.65 | 14.3% | 71.4% | 19.8% |
| A always waits next to the fixed B, seed 0 | -56.16 | 34.4 | 99.3% | 0.0% | undefined |
| A always waits next to the fixed B, seed 1 | -40.23 | 19.58 | 40.6% | 0.0% | undefined |
| A always waits next to the fixed B, seed 2 | -44.27 | 23.83 | 54.3% | 0.0% | undefined |
| A always waits next to the fixed B, seed 3 | -56.3 | 34.64 | 100.0% | 0.0% | undefined |
| A always waits next to the fixed B, seed 4 | -40.04 | 21.05 | 45.1% | 0.0% | undefined |

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
