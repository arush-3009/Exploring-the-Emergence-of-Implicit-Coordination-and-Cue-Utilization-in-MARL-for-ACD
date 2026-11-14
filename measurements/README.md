# Measurements

Turns the saved episode records into statistics to understand agent behaviour.
The input is the saved episode records, the output is the CSV tables that the figures read.


## Computing the stats -

1. [episode.py](episode.py) turns one record into one row of `episodes.csv`. For every
   measurement the row holds the episode's contribution and whether the episode counts at all.
   An episode with no intrusion has nothing to say about B's response, for example, so it is
   left out of that measurement. [interruptions.py](interruptions.py),
   [opportunities.py](opportunities.py) and [decisions.py](decisions.py) list the single events
   the sender measurements are built from.
2. [team.py](team.py) adds those rows up for one team, over all of its evaluation episodes
   and also per evaluation seed. A rate is added as numerator and denominator and divided once
   at the end, so a rate over decisions or interruptions is pooled over all of them. [controls.py](controls.py) does the same for a control run
   and keeps the difference against the normal evaluation, since both played the same
   episodes. [probe.py](probe.py) is the same-input probe. [training_series.py](training_series.py)
   summarises what A did during training.
3. [arm.py](arm.py) takes the five teams of one arm and writes their mean, standard deviation,
   minimum, maximum and how many of them had a value. The mean is only over the teams that
   had one.
4. [world.py](world.py) and [study.py](study.py) put the arms, the controls and the baselines
   of one world, and then of one study, next to each other.
