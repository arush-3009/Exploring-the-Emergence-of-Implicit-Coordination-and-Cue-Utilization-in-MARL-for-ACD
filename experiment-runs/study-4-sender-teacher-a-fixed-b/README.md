# Study 4, A from the teacher next to a fixed B

The study's five worlds side by side. A value is the mean over the arm's teams that have a value, with their number in brackets. Each world's README lists its teams one by one.

## The worlds

| world | arm | team reward per episode | B's infected server-intervals per intrusion episode | intrusion episodes ending with an infected B server | A interrupted the attacked pair's server after the intrusion | B responded to A's interruption |
|---|---|---|---|---|---|---|
| [reliable warnings](worlds/reliable-warnings/README.md) | cue-visible | -27.72 (5 teams) | 8.68 (5 teams) | 0.0% (5 teams) | 59.3% (5 teams) | 100.0% (5 teams) |
| [reliable warnings](worlds/reliable-warnings/README.md) | cue-hidden-failures-suppressed | -31.9 (5 teams) | 13.34 (5 teams) | 12.8% (5 teams) | 0.07% (5 teams) | 0.0% (1 teams) |
| [one false warning](worlds/one-false-warning/README.md) | cue-visible | -30.7 (5 teams) | 9.872 (5 teams) | 3.7% (5 teams) | 65.7% (5 teams) | 97.4% (4 teams) |
| [one false warning](worlds/one-false-warning/README.md) | cue-hidden-failures-suppressed | -46.58 (5 teams) | 25.14 (5 teams) | 59.5% (5 teams) | 0.0% (5 teams) | undefined (0 teams) |
| [two false warnings](worlds/two-false-warnings/README.md) | cue-visible | -32.6 (5 teams) | 10.53 (5 teams) | 7.2% (5 teams) | 64.0% (5 teams) | 98.9% (5 teams) |
| [two false warnings](worlds/two-false-warnings/README.md) | cue-hidden-failures-suppressed | -48.42 (5 teams) | 26.6 (5 teams) | 67.7% (5 teams) | 1.2% (5 teams) | 3.1% (3 teams) |
| [one false warning missed warnings](worlds/one-false-warning-missed-warnings/README.md) | cue-visible | -36.3 (5 teams) | 13.15 (5 teams) | 11.6% (5 teams) | 38.7% (5 teams) | 99.7% (3 teams) |
| [one false warning missed warnings](worlds/one-false-warning-missed-warnings/README.md) | cue-hidden-failures-suppressed | -43.84 (5 teams) | 18.37 (5 teams) | 30.3% (5 teams) | 0.70% (5 teams) | 1.1% (2 teams) |
| [one false warning missed warnings outages](worlds/one-false-warning-missed-warnings-outages/README.md) | cue-visible | -47.11 (5 teams) | 14.61 (5 teams) | 16.7% (5 teams) | 0.0% (5 teams) | undefined (0 teams) |
| [one false warning missed warnings outages](worlds/one-false-warning-missed-warnings-outages/README.md) | cue-hidden-failures-suppressed | -46.83 (5 teams) | 15.17 (5 teams) | 18.2% (5 teams) | 0.0% (5 teams) | undefined (0 teams) |

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
