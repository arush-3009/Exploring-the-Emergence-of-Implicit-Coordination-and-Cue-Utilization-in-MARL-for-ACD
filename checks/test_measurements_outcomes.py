import pytest

from checks.record_builder import WORLD, Episode
from measurements.episode import episode_columns, measure_episode


def row_of(episode, sender=False):
    return measure_episode(episode.record(), WORLD, sender)


def test_reward_is_the_sum_of_the_shared_reward_over_the_episode():
    episode = Episode()
    episode.reward(3, -2.5)
    episode.reward(40, -1.0)
    assert (row_of(episode)["reward"], row_of(episode)["reward_eligible"]) == (-3.5, 1)


def test_b_infection_counts_server_intervals_and_the_final_boundary_on_intrusion_episodes_only():
    episode = Episode(intrusion=("A2", 10))
    episode.spread("A2", 12)
    row = row_of(episode)
    assert (row["b_infected_intervals"], row["b_infected_intervals_eligible"]) == (38, 1)
    assert (row["b_infected_end"], row["b_infected_end_eligible"]) == (1, 1)
    assert (row["final_compromised_B1"], row["final_compromised_B2"], row["final_compromised_B3"]) == (0, 1, 0)
    assert row["intrusion_server"] == "A2" and row["intrusion_interval"] == 10
    assert measure_episode(episode.record(), WORLD, sender=True)["a_infected_intervals"] == 40


def test_a_b_server_cleaned_before_the_final_boundary_leaves_no_infection_and_isolation_is_not_clearance():
    episode = Episode(intrusion=("B2", 10))
    episode.act("B", 20, "restore", "B2", busy=3)
    episode.set("B2", 20, isolated=True, service_running=False)
    episode.complete("B", 23, "restore")
    row = row_of(episode)
    assert (row["b_infected_intervals"], row["b_infected_end"]) == (13, 0)

    episode = Episode(intrusion=("B2", 10))
    episode.act("B", 20, "isolate", "B2")
    episode.set("B2", 20, isolated=True)
    assert row_of(episode)["b_infected_end"] == 1


def test_a_restore_still_running_at_the_horizon_counts_by_the_final_truth():
    episode = Episode(intrusion=("B3", 10))
    episode.act("B", 48, "restore", "B3", busy=1)
    episode.set("B3", 48, isolated=True, service_running=False)
    assert row_of(episode)["b_infected_end"] == 1


def test_a_no_intrusion_episode_is_outside_the_infection_measurements():
    row = row_of(Episode())
    for id in ("b_infected_intervals", "b_infected_end"):
        assert (row[id], row[f"{id}_eligible"]) == (None, 0)
    assert row["intrusion_server"] is None and row["relevant_b_server"] is None


def test_failed_requests_count_every_failed_required_request_whichever_end_caused_it():
    episode = Episode()
    episode.set("A2", 10, 11, isolated=True)
    assert row_of(episode)["failed_requests"] == 2 * 3


def test_inspections_count_accepted_starts_per_defender_once_per_job():
    episode = Episode()
    episode.act("A", 5, "inspect", "A1", busy=1)
    episode.act("A", 9, "inspect", "A2", busy=1)
    episode.act("B", 5, "inspect", "B1", busy=1)
    episode.act("B", 8, "inspect", "B2", result="rejected")
    row = row_of(episode)
    assert (row["inspections_a"], row["inspections_b"]) == (2, 1)


def test_clean_restores_use_the_truth_when_the_job_starts():
    episode = Episode(intrusion=("B1", 10))
    episode.act("B", 5, "restore", "B2", busy=3)
    episode.act("B", 12, "restore", "B1", busy=3)
    episode.act("A", 5, "restore", "A1", busy=3)
    row = row_of(episode)
    assert (row["clean_restores_b"], row["clean_restores_a"]) == (1, 1)


def test_the_row_has_exactly_the_episode_columns_and_the_script_as_text():
    episode = Episode(intrusion=("A3", 7), missed=("B3", "A1"), false_warnings=[("A2", 5), ("B1", 12)],
                      outages=[("B2", 14, 3)])
    row = measure_episode(episode.record(episode=4, evaluation_seed=2002), WORLD, sender=True)
    assert list(row) != [] and set(row) == set(episode_columns(WORLD))
    assert (row["episode"], row["evaluation_seed"], row["iteration"]) == (4, 2002, None)
    assert (row["false_warnings"], row["missed_servers"], row["outages"]) == ("A2@5;B1@12", "B3;A1", "B2@14+3")
    assert (row["relevant_a_server"], row["relevant_b_server"], row["relevant_b_monitoring_missed"]) == ("A3", "B3", 1)


def test_a_training_row_carries_its_iteration():
    row = measure_episode(Episode().record(episode=3, evaluation_seed=None, iteration=17), WORLD, sender=True)
    assert (row["episode"], row["evaluation_seed"], row["iteration"]) == (3, None, 17)


def test_a_free_entry_without_a_result_or_a_busy_entry_with_a_choice_fails():
    record = Episode().record()
    record.intervals[12]["defenders"]["B"]["result"] = None
    with pytest.raises(ValueError, match="free, action and result disagree"):
        measure_episode(record, WORLD, sender=False)

    record = Episode().record()
    record.intervals[12]["defenders"]["A"]["free"] = False
    with pytest.raises(ValueError, match="free, action and result disagree"):
        measure_episode(record, WORLD, sender=False)


def test_a_request_list_that_does_not_match_the_reward_s_failed_count_fails():
    episode = Episode()
    episode.set("A2", 5, 5, isolated=True)
    record = episode.record()
    record.intervals[5]["requests"] = []
    with pytest.raises(ValueError, match="failed requests"):
        measure_episode(record, WORLD, sender=False)
