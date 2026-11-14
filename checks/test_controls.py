import pytest

from checks.record_builder import WORLD, Episode, pick
from measurements.controls import control_measurements, paired_columns
from measurements.episode import episode_columns, measure_episode
from measurements.tables import read_csv, write_csv
from measurements.team import team_measurements


def evaluation(tmp_path, name, records, sender=True):
    rows = []
    for record in records:
        rows.append(measure_episode(record, WORLD, sender))
    write_csv(tmp_path / name / "episodes.csv", rows, episode_columns(WORLD))
    return read_csv(tmp_path / name / "episodes.csv")


def infected_b2(responds_at, seed=2001, episode=0, **masks):

    record = Episode(intrusion=("A2", 10), **masks)
    record.spread("A2", 12)
    record.act("A", 14, "isolate", "A2")
    record.set("A2", 14, isolated=True)
    if responds_at is not None:
        record.act("B", responds_at, "restore", "B2", busy=3)
        record.set("B2", responds_at, isolated=True, service_running=False)
        record.complete("B", responds_at + 3, "restore")
    return record.record(episode=episode, evaluation_seed=seed)


def by_id(rows):
    result = {}
    for row in rows:
        result[row["id"]] = row
    return result


def test_the_control_difference_is_normal_minus_control_on_the_same_episodes(tmp_path):
    normal = evaluation(tmp_path, "normal", [infected_b2(15, episode=0), infected_b2(15, seed=2002, episode=0)])
    control = evaluation(tmp_path, "control", [infected_b2(25, episode=0, suppress=("B",)),
                                               infected_b2(None, seed=2002, episode=0, suppress=("B",))])
    paired, ctrl = control_measurements(normal, control, sender=True)
    write_csv(tmp_path / "paired.csv", paired, paired_columns(True))
    assert pick(read_csv(tmp_path / "paired.csv"), "evaluation_seed") == ["2001", "2002"]

    rows = by_id(ctrl)
    infected = rows["ctrl_b_infected_intervals"]
    assert (infected["numerator"], infected["denominator"], infected["value"]) == (-10.0 - 32.0, 2, -21.0)
    assert (infected["value_2001"], infected["value_2002"]) == (-10.0, -32.0)
    assert rows["ctrl_b_infected_end"]["value"] == -0.5
    assert rows["ctrl_a_interrupts"]["value"] == 0.0
    responds = rows["ctrl_b_responds_to_a"]
    assert (responds["value"], responds["numerator"], responds["denominator"]) == (1.0, None, None)
    assert (responds["value_2001"], responds["value_2002"]) == (1.0, 1.0)
    assert pick(paired, "b_responds_to_a_numerator_normal", "b_responds_to_a_denominator_normal") == [
        ("1", "1"), ("1", "1")]
    assert pick(paired, "b_responds_to_a_numerator_control", "b_responds_to_a_denominator_control") == [
        ("0", "1"), ("0", "1")]


def test_the_response_difference_pools_each_evaluation_over_its_own_interruptions(tmp_path):
    row = evaluation(tmp_path, "normal", [infected_b2(15)])[0]
    normal = []
    control = []
    for episode, (normal_counts, control_counts) in enumerate((((5, 6), (1, 2)), ((3, 4), (0, 2)))):
        for rows, (numerator, denominator) in ((normal, normal_counts), (control, control_counts)):
            rows.append(dict(row, episode=str(episode), b_responds_to_a_numerator=str(numerator),
                             b_responds_to_a_denominator=str(denominator)))
    _, ctrl = control_measurements(normal, control, sender=True)
    responds = by_id(ctrl)["ctrl_b_responds_to_a"]
    assert responds["value"] == pytest.approx(0.55)
    assert (responds["numerator"], responds["denominator"]) == (None, None)

    rates = []
    for rows in (normal, control):
        for measured in team_measurements(rows, None, True):
            if measured["id"] == "b_responds_to_a":
                rates.append((measured["value"], measured["numerator"], measured["denominator"]))
    assert rates == [(0.8, 8.0, 10), (0.25, 1.0, 4)]
    assert rates[0][0] - rates[1][0] == pytest.approx(responds["value"])


def test_ctrl_b_responds_to_a_is_undefined_when_either_evaluation_has_no_eligible_interruption(tmp_path):
    quiet = Episode(intrusion=("A2", 10)).record()
    normal = evaluation(tmp_path, "normal", [infected_b2(15)])
    control = evaluation(tmp_path, "control", [quiet])
    _, ctrl = control_measurements(normal, control, sender=True)
    assert by_id(ctrl)["ctrl_b_responds_to_a"]["value"] is None


def test_study_1_controls_pair_only_the_study_1_measurements(tmp_path):
    normal = evaluation(tmp_path, "normal", [infected_b2(15)], sender=False)
    control = evaluation(tmp_path, "control", [infected_b2(25, hide=("B",))], sender=False)
    paired, ctrl = control_measurements(normal, control, sender=False)
    assert pick(ctrl, "id") == ["ctrl_reward", "ctrl_b_infected_intervals", "ctrl_b_infected_end",
                                           "ctrl_b_unprompted_enabled", "ctrl_b_unprompted_missed"]
    assert set(paired[0]) == set(paired_columns(False))


def test_the_two_evaluations_must_hold_the_same_episodes_with_the_same_scripts(tmp_path):
    normal = evaluation(tmp_path, "normal", [infected_b2(15, episode=0)])
    other_episode = evaluation(tmp_path, "other", [infected_b2(15, episode=1)])
    with pytest.raises(ValueError, match="same episodes"):
        control_measurements(normal, other_episode, sender=True)

    other_script = evaluation(tmp_path, "script", [Episode(intrusion=("A3", 10)).record()])
    with pytest.raises(ValueError, match="scripts differ"):
        control_measurements(normal, other_script, sender=True)


def test_two_rows_of_the_same_episode_fail(tmp_path):
    normal = evaluation(tmp_path, "normal", [infected_b2(15), infected_b2(15)])
    with pytest.raises(ValueError, match="two rows"):
        control_measurements(normal, normal, sender=True)
