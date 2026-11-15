# Study 2, both defenders from the teacher, both learning

The study's five worlds side by side. A value is the mean over the arm's teams that have a value, with their number in brackets. Each world's README lists its teams one by one.

## The worlds

| world | arm | team reward per episode | B's infected server-intervals per intrusion episode | intrusion episodes ending with an infected B server | A interrupted the attacked pair's server after the intrusion | B responded to A's interruption |
|---|---|---|---|---|---|---|
| [reliable warnings](worlds/reliable-warnings/README.md) | cue-visible | -28.16 (5 teams) | 10.52 (5 teams) | 0.0% (5 teams) | 0.0% (5 teams) | undefined (0 teams) |
| [reliable warnings](worlds/reliable-warnings/README.md) | cue-hidden-failures-suppressed | -28.25 (5 teams) | 10.42 (5 teams) | 0.0% (5 teams) | 0.0% (5 teams) | undefined (0 teams) |
| [one false warning](worlds/one-false-warning/README.md) | cue-visible | -29.76 (5 teams) | 11.04 (5 teams) | 0.0% (5 teams) | 0.0% (5 teams) | undefined (0 teams) |
| [one false warning](worlds/one-false-warning/README.md) | cue-hidden-failures-suppressed | -30.28 (5 teams) | 10.92 (5 teams) | 0.26% (5 teams) | 0.0% (5 teams) | undefined (0 teams) |
| [two false warnings](worlds/two-false-warnings/README.md) | cue-visible | -30.89 (5 teams) | 11.18 (5 teams) | 0.15% (5 teams) | 0.01% (5 teams) | 50.0% (1 teams) |
| [two false warnings](worlds/two-false-warnings/README.md) | cue-hidden-failures-suppressed | -31.13 (5 teams) | 11.89 (5 teams) | 3.0% (5 teams) | 0.0% (5 teams) | undefined (0 teams) |
| [one false warning missed warnings](worlds/one-false-warning-missed-warnings/README.md) | cue-visible | -37.17 (5 teams) | 14.9 (5 teams) | 17.5% (5 teams) | 0.79% (5 teams) | 38.3% (1 teams) |
| [one false warning missed warnings](worlds/one-false-warning-missed-warnings/README.md) | cue-hidden-failures-suppressed | -36.98 (5 teams) | 15.62 (5 teams) | 18.4% (5 teams) | 0.0% (5 teams) | undefined (0 teams) |
| [one false warning missed warnings outages](worlds/one-false-warning-missed-warnings-outages/README.md) | cue-visible | -44.8 (5 teams) | 15.25 (5 teams) | 17.5% (5 teams) | 0.0% (5 teams) | undefined (0 teams) |
| [one false warning missed warnings outages](worlds/one-false-warning-missed-warnings-outages/README.md) | cue-hidden-failures-suppressed | -45.19 (5 teams) | 15.08 (5 teams) | 16.9% (5 teams) | 0.0% (5 teams) | undefined (0 teams) |

Every mean of the study with its standard deviation and number of teams, the baselines and the control differences are in [master_table.csv](master_table.csv). [measurements.csv](measurements.csv) gives every measurement's id, name, population and denominator.

## Figures

### How well do the teams defend?

![How well do the teams defend?](figures/S1-performance.png)

The points drawn are in [figures/S1-performance.csv](figures/S1-performance.csv), the vector version in [figures/S1-performance.svg](figures/S1-performance.svg).

### Does A interrupt its servers in ways B can see, and does B respond?

![Does A interrupt its servers in ways B can see, and does B respond?](figures/S2-signalling.png)

The points drawn are in [figures/S2-signalling.csv](figures/S2-signalling.csv), the vector version in [figures/S2-signalling.svg](figures/S2-signalling.svg).

### What do the cue-visible teams lose when the cue is removed at evaluation?

![What do the cue-visible teams lose when the cue is removed at evaluation?](figures/S3-controls.png)

The points drawn are in [figures/S3-controls.csv](figures/S3-controls.csv), the vector version in [figures/S3-controls.svg](figures/S3-controls.svg).

### Given the same inputs, how likely is A to interrupt?

![Given the same inputs, how likely is A to interrupt?](figures/S4-probe.png)

The points drawn are in [figures/S4-probe.csv](figures/S4-probe.csv), the vector version in [figures/S4-probe.svg](figures/S4-probe.svg).

## Worlds

- [reliable warnings](worlds/reliable-warnings/README.md)
- [one false warning](worlds/one-false-warning/README.md)
- [two false warnings](worlds/two-false-warnings/README.md)
- [one false warning missed warnings](worlds/one-false-warning-missed-warnings/README.md)
- [one false warning missed warnings outages](worlds/one-false-warning-missed-warnings-outages/README.md)
