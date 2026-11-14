import pytest

from checks.record_builder import WORLD, Episode, pick
from measurements.opportunities import opportunities_of


def only(episode):
    rows = opportunities_of(episode.record(), WORLD)
    assert len(rows) == 1
    return rows[0]


def test_a_restore_started_while_infected_qualifies_before_its_completion_closes_the_window():
    episode = Episode(intrusion=("A1", 10))
    episode.warn("A", "A1", 13)
    episode.act("A", 13, "restore", "A1", busy=3)
    episode.set("A1", 13, isolated=True, service_running=False)
    episode.complete("A", 16, "restore")
    row = only(episode)
    assert (row["server"], row["boundary"], row["status"], row["a_warning"]) == ("A1", 13, "infected", 1)
    assert (row["close_interval"], row["close_event"], row["first_interruption_interval"], row["score"]) == (
        16, "restore", 13, 1)


def test_a_change_before_a_start_in_the_same_interval_puts_that_start_outside_the_window():
    episode = Episode(intrusion=("A2", 8))
    episode.warn("A", "A2", 5)
    episode.act("A", 8, "isolate", "A2")
    episode.set("A2", 8, isolated=True)
    row = only(episode)
    assert (row["boundary"], row["status"], row["close_interval"], row["close_event"]) == (5, "clean", 8, "intrusion")
    assert (row["first_interruption_interval"], row["score"]) == (None, 0)


def test_a_change_after_a_start_in_the_same_interval_leaves_that_start_inside_the_window():
    episode = Episode(intrusion=("B1", 3))
    episode.warn("A", "A1", 5)
    episode.act("A", 8, "isolate", "A1")
    episode.spread("B1", 8)
    episode.set("A1", 8, isolated=True)
    row = only(episode)
    assert (row["status"], row["close_interval"], row["close_event"], row["score"]) == ("clean", 8, "spread", 1)


def test_a_clean_opportunity_followed_by_infection_cleanup_and_a_clean_interruption_does_not_qualify():
    episode = Episode(intrusion=("B2", 3))
    episode.warn("A", "A2", 5, 11)
    episode.spread("B2", 7)
    episode.act("A", 9, "restore", "A2", busy=3)
    episode.set("A2", 9, 11, isolated=True, service_running=False)
    episode.complete("A", 12, "restore")
    episode.act("A", 20, "isolate", "A2")
    episode.set("A2", 20, isolated=True)
    row = only(episode)
    assert (row["boundary"], row["status"], row["close_interval"], row["close_event"]) == (5, "clean", 7, "spread")
    assert row["score"] == 0


def test_a_window_without_a_status_change_closes_at_episode_end_and_is_kept_without_an_interruption():
    episode = Episode()
    episode.warn("A", "A3", 30)
    row = only(episode)
    assert (row["status"], row["close_interval"], row["close_event"], row["score"]) == ("clean", None, "episode end", 0)


def test_an_infected_finding_is_evidence_and_the_opportunity_is_the_first_free_boundary_with_evidence():
    episode = Episode(intrusion=("A1", 10))
    episode.find("A", "A1", "infected", 14)
    episode.act("A", 12, "inspect", "A2", busy=3)
    episode.warn("A", "A1", 20)
    row = only(episode)
    assert (row["boundary"], row["status"], row["a_warning"], row["a_finding"]) == (16, "infected", 0, "infected")


def test_evidence_about_a_server_that_is_isolated_or_stopped_in_hidden_truth_is_no_opportunity():
    episode = Episode()
    episode.set("A1", 4, 9, isolated=True)
    episode.warn("A", "A1", 5)
    assert only(episode)["boundary"] == 11

    episode = Episode()
    episode.set("A1", 4, service_running=False)
    episode.warn("A", "A1", 5)
    assert opportunities_of(episode.record(), WORLD) == []


def test_there_is_at_most_one_opportunity_per_server_and_the_window_never_reopens():
    episode = Episode(intrusion=("A1", 10))
    episode.warn("A", "A1", 5, 6)
    episode.act("A", 13, "restore", "A1", busy=3)
    episode.set("A1", 13, isolated=True, service_running=False)
    episode.complete("A", 16, "restore")
    episode.warn("A", "A1", 30)
    row = only(episode)
    assert (row["boundary"], row["status"], row["close_event"], row["close_interval"], row["score"]) == (
        5, "clean", "intrusion", 10, 0)


def test_one_opportunity_per_a_server():
    episode = Episode()
    episode.warn("A", "A1", 5)
    episode.warn("A", "A3", 8)
    episode.warn("B", "B2", 4)
    rows = opportunities_of(episode.record(), WORLD)
    assert pick(rows, "server", "boundary") == [("A1", 5), ("A3", 8)]


def test_a_record_whose_events_do_not_explain_its_truth_fails():
    record = Episode().record()
    record.intervals[20]["servers"]["A2"]["compromised"] = True
    with pytest.raises(ValueError, match="does not match the recorded truth"):
        opportunities_of(record, WORLD)


def test_episodes_csv_carries_each_episode_s_opportunity_counts_by_class():
    from measurements.episode import measure_episode

    episode = Episode(intrusion=("A1", 10))
    episode.warn("A", "A1", 13)
    episode.act("A", 13, "isolate", "A1")
    episode.set("A1", 13, isolated=True)
    episode.warn("A", "A2", 5)
    episode.warn("A", "A3", 6)
    episode.act("A", 6, "restore", "A3", busy=3)
    episode.set("A3", 6, isolated=True, service_running=False)
    row = measure_episode(episode.record(), WORLD, sender=True)
    assert (row["a_interrupt_on_evidence_infected_numerator"], row["a_interrupt_on_evidence_infected_denominator"]) == (1, 1)
    assert (row["a_interrupt_on_evidence_clean_numerator"], row["a_interrupt_on_evidence_clean_denominator"]) == (1, 2)
