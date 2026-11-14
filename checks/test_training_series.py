import pytest

from checks.record_builder import WORLD, Episode, pick
from measurements.episode import episode_columns, measure_episode
from measurements.tables import read_csv, write_csv
from measurements.training_series import training_behaviour, training_columns


def test_one_row_per_block_of_100_iterations_with_pooled_counts(tmp_path):
    episodes = []
    for iteration in (1, 100, 101, 250):
        record = Episode(intrusion=("A1", 10))
        if iteration != 100:
            record.act("A", 14, "isolate", "A1")
            record.set("A1", 14, isolated=True)
        record = record.record(episode=0, evaluation_seed=None, iteration=iteration)
        episodes.append(measure_episode(record, WORLD, sender=True))
    write_csv(tmp_path / "training_episodes.csv", episodes, episode_columns(WORLD))

    rows = training_behaviour(read_csv(tmp_path / "training_episodes.csv"))
    write_csv(tmp_path / "training_behaviour.csv", rows, training_columns())
    assert pick(rows, "block", "first_iteration", "last_iteration", "episodes") == [
        (1, 1, 100, 2), (2, 101, 101, 1), (3, 250, 250, 1)]
    assert (rows[0]["a_interrupts"], rows[0]["a_interrupts_numerator"], rows[0]["a_interrupts_denominator"]) == (
        0.5, 1.0, 2)
    assert (rows[0]["a_interrupt_relevant"], rows[0]["b_responds_to_a"], rows[0]["b_responds_to_a_denominator"]) == (
        0.5, 0.0, 1)
    assert (rows[0]["a_interrupt_on_evidence_infected"], rows[0]["a_interrupt_on_evidence_infected_denominator"]) == (
        None, 0)
    assert rows[1]["a_isolates"] == rows[2]["a_isolates"] == 1.0


@pytest.mark.parametrize(("iterations", "blocks"), [(3, [(1, 1, 3, 6)]),
                                                   (100, [(1, 1, 100, 200)]),
                                                   (103, [(1, 1, 100, 200), (2, 101, 103, 6)])])
def test_a_block_ends_where_training_ended(iterations, blocks, tmp_path):
    episodes = []
    for iteration in range(1, iterations + 1):
        for episode in (0, 1):
            record = Episode().record(episode=episode, evaluation_seed=None, iteration=iteration)
            episodes.append(measure_episode(record, WORLD, sender=True))
    write_csv(tmp_path / "training_episodes.csv", episodes, episode_columns(WORLD))

    rows = training_behaviour(read_csv(tmp_path / "training_episodes.csv"))
    assert pick(rows, "block", "first_iteration", "last_iteration", "episodes") == blocks


def test_two_rows_of_the_same_training_episode_fail(tmp_path):
    row = measure_episode(Episode().record(episode=3, evaluation_seed=None, iteration=7), WORLD, sender=True)
    write_csv(tmp_path / "training_episodes.csv", [row, row], episode_columns(WORLD))
    with pytest.raises(ValueError, match="two rows"):
        training_behaviour(read_csv(tmp_path / "training_episodes.csv"))
