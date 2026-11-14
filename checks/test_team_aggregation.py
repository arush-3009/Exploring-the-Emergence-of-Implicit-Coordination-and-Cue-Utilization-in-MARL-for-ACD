import pytest

from checks.record_builder import WORLD, Episode, pick
from measurements.episode import episode_columns, measure_episode
from measurements.tables import read_csv, write_csv
from measurements.team import team_columns, team_measurements


def episodes_csv(tmp_path, records, sender=True):
    rows = []
    for record in records:
        rows.append(measure_episode(record, WORLD, sender))
    write_csv(tmp_path / "episodes.csv", rows, episode_columns(WORLD))
    return read_csv(tmp_path / "episodes.csv")


def by_id(rows):
    result = {}
    for row in rows:
        result[row["id"]] = row
    return result


def peer_failures(waits, responds, seed, episode):

    record = Episode()
    record.set("A2", 9, 9 + waits + int(responds) - 1, isolated=True)
    if responds:
        record.act("B", 10 + waits, "inspect", "B2", busy=1)
    return record.record(episode=episode, evaluation_seed=seed)


def test_rates_are_pooled_counts_not_averages_of_episode_rates(tmp_path):
    records = [peer_failures(0, True, 2001, 0), peer_failures(3, False, 2001, 1)]
    row = by_id(team_measurements(episodes_csv(tmp_path, records), None, True))["b_acts_on_peer_failure"]
    assert (row["value"], row["numerator"], row["denominator"]) == (0.25, 1.0, 4)


def test_the_team_reward_is_the_mean_episode_reward_and_each_evaluation_seed_is_shown_separately(tmp_path):
    records = []
    for index, (seed, value) in enumerate([(2001, -38.0), (2001, -34.0), (2002, -36.0), (2002, -36.0)]):
        episode = Episode()
        episode.reward(0, value)
        for t in range(1, 50):
            episode.reward(t, 0.0)
        records.append(episode.record(episode=index, evaluation_seed=seed))
    rows = team_measurements(episodes_csv(tmp_path, records), None, True)
    reward = by_id(rows)["reward"]
    assert (reward["value"], reward["numerator"], reward["denominator"]) == (-36.0, -144.0, 4)
    assert (reward["value_2001"], reward["denominator_2001"], reward["value_2002"], reward["denominator_2002"]) == (
        -36.0, 2, -36.0, 2)
    assert list(rows[0]) == team_columns(["2001", "2002"])


def test_an_empty_denominator_gives_no_value_never_a_zero(tmp_path):
    records = [Episode().record(episode=0), Episode(intrusion=("A2", 10)).record(episode=1)]
    rows = by_id(team_measurements(episodes_csv(tmp_path, records), None, True))
    for id in ("b_acts_on_peer_failure", "a_interrupt_relevant_b_closed", "a_interrupt_b_unaware",
               "b_responds_to_a", "a_interrupt_on_evidence_infected", "b_unprompted_missed"):
        assert (rows[id]["value"], rows[id]["numerator"], rows[id]["denominator"]) == (None, 0.0, 0), id
    assert (rows["b_infected_intervals"]["value"], rows["b_infected_intervals"]["denominator"]) == (0.0, 1)

    write_csv(tmp_path / "team_measurements.csv", list(rows.values()), team_columns(["2001"]))
    written = by_id(read_csv(tmp_path / "team_measurements.csv"))
    assert (written["b_responds_to_a"]["value"], written["b_responds_to_a"]["denominator"]) == ("", "0")


def test_interruptions_and_opportunities_are_pooled_by_their_own_rules(tmp_path):
    first = Episode(intrusion=("A1", 10))
    first.warn("A", "A1", 13)
    first.act("A", 13, "isolate", "A1")
    first.set("A1", 13, isolated=True)
    first.act("B", 14, "restore", "B1", busy=3)
    second = Episode(intrusion=("A2", 10))
    second.warn("A", "A2", 13)
    second.warn("A", "A3", 5)
    second.act("A", 13, "isolate", "A2")
    second.set("A2", 13, isolated=True)
    rows = by_id(team_measurements(episodes_csv(tmp_path, [first.record(episode=0), second.record(episode=1)]),
                                   None, True))
    assert (rows["b_responds_to_a"]["numerator"], rows["b_responds_to_a"]["denominator"]) == (1.0, 2)
    assert (rows["a_interrupt_on_evidence_infected"]["numerator"],
            rows["a_interrupt_on_evidence_infected"]["denominator"]) == (2.0, 2)
    assert (rows["a_interrupt_on_evidence_clean"]["numerator"],
            rows["a_interrupt_on_evidence_clean"]["denominator"]) == (0.0, 1)


def test_study_1_has_no_sender_rows_and_a_sender_team_adds_its_probe_and_before_rows(tmp_path):
    records = [Episode().record()]
    receiver = team_measurements(episodes_csv(tmp_path, records, sender=False), None, False)
    assert pick(receiver, "id") == ["reward", "b_infected_intervals", "b_infected_end", "failed_requests",
                                               "inspections_a", "inspections_b", "b_unprompted_enabled",
                                               "b_unprompted_missed", "b_acts_on_peer_failure", "clean_restores_b",
                                               "clean_restores_a"]

    episodes = episodes_csv(tmp_path, records)
    probe = [{"id": "probe_interrupt_warning", "value": 0.5, "numerator": 1.0, "denominator": 2}]
    write_csv(tmp_path / "before.csv", team_measurements(episodes, probe, True),
              team_columns(["2001"]))
    before = read_csv(tmp_path / "before.csv")
    rows = team_measurements(episodes, probe, True, before=before)
    ids = by_id(rows)
    assert (ids["probe_interrupt_warning"]["value"], ids["probe_interrupt_warning"]["value_2001"]) == (0.5, None)
    assert ids["before_probe_interrupt_warning"]["value"] == "0.5"
    assert ids["before_reward"]["value"] == ids["before_reward"]["value_2001"] == str(ids["reward"]["value"])
    assert len(rows) == 2 * (22 + 1)


def test_two_rows_of_the_same_episode_fail(tmp_path):
    record = Episode().record()
    with pytest.raises(ValueError, match="two rows"):
        team_measurements(episodes_csv(tmp_path, [record, record]), None, True)
