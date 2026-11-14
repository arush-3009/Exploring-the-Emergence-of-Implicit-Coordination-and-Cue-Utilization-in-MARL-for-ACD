import pytest

from checks.record_builder import WORLD, Episode
from measurements.episode import measure_episode


def scored(episode):
    row = measure_episode(episode.record(), WORLD, sender=False)
    assert row["b_unprompted_enabled_eligible"] == 1 and row["b_unprompted_missed_eligible"] == 0
    return row["b_unprompted_enabled"]


def test_no_warning_and_an_unknown_finding():
    episode = Episode(intrusion=("B1", 10))
    episode.act("B", 12, "inspect", "B1", busy=1)
    assert scored(episode) == 1


def test_a_warning_cleared_by_a_completed_inspect_before_the_intrusion_leaves_a_clean_finding():
    episode = Episode(intrusion=("B1", 10))
    episode.warn("B", "B1", 3, 4)
    episode.act("B", 3, "inspect", "B1", busy=1)
    episode.complete("B", 4, "inspect")
    episode.find("B", "B1", "clean", 5)
    episode.act("B", 12, "inspect", "B1", busy=1)
    assert scored(episode) == 1


def test_a_warning_received_at_boundary_3_still_visible():
    episode = Episode(intrusion=("B1", 10))
    episode.warn("B", "B1", 3)
    episode.act("B", 12, "inspect", "B1", busy=1)
    assert scored(episode) == 0


def test_a_warning_already_visible_at_boundary_12():
    episode = Episode(intrusion=("B1", 10))
    episode.warn("B", "B1", 12)
    episode.act("B", 12, "restore", "B1", busy=3)
    assert scored(episode) == 0


def test_a_warning_delivered_during_interval_12_is_visible_only_at_13():
    episode = Episode(intrusion=("B1", 10))
    episode.warn("B", "B1", 13)
    episode.act("B", 12, "inspect", "B1", busy=1)
    assert scored(episode) == 1


def test_an_infected_finding_is_visible():
    episode = Episode(intrusion=("B1", 10))
    episode.find("B", "B1", "infected", 11)
    episode.act("B", 12, "restore", "B1", busy=3)
    assert scored(episode) == 0


def test_only_the_first_response_is_scored_though_its_inspect_later_clears_the_warning():
    episode = Episode(intrusion=("B1", 10))
    episode.warn("B", "B1", 11, 13)
    episode.act("B", 12, "inspect", "B1", busy=1)
    episode.complete("B", 13, "inspect")
    episode.find("B", "B1", "infected", 14)
    episode.act("B", 20, "restore", "B1", busy=3)
    assert scored(episode) == 0


def test_an_inspect_without_evidence_whose_result_later_reports_infection():
    episode = Episode(intrusion=("B1", 10))
    episode.act("B", 12, "inspect", "B1", busy=1)
    episode.complete("B", 13, "inspect")
    episode.find("B", "B1", "infected", 14)
    assert scored(episode) == 1


def test_a_restore_without_evidence_whose_cleanup_prevents_any_later_warning():
    episode = Episode(intrusion=("B1", 10))
    episode.act("B", 12, "restore", "B1", busy=3)
    episode.set("B1", 12, isolated=True, service_running=False)
    episode.complete("B", 15, "restore")
    assert scored(episode) == 1


def test_an_isolate_without_evidence_counts_though_it_cleans_nothing():
    episode = Episode(intrusion=("B1", 10))
    episode.act("B", 12, "isolate", "B1")
    episode.complete("B", 12, "isolate")
    episode.set("B1", 12, isolated=True)
    assert scored(episode) == 1


def test_an_isolate_with_a_visible_warning_is_the_first_response_and_later_choices_cannot_replace_it():
    episode = Episode(intrusion=("B1", 10))
    episode.warn("B", "B1", 12, 12)
    episode.act("B", 12, "isolate", "B1")
    episode.set("B1", 12, isolated=True)
    episode.act("B", 20, "restore", "B1", busy=3)
    assert scored(episode) == 0


@pytest.mark.parametrize("action, result", [("wait", "accepted"), ("reconnect", "accepted")])
def test_waiting_or_reconnecting_is_no_response(action, result):
    episode = Episode(intrusion=("B1", 10))
    episode.set("B1", 11, 11, isolated=True)
    episode.act("B", 12, action, None if action == "wait" else "B1", result=result)
    row = measure_episode(episode.record(), WORLD, sender=False)
    assert (row["b_unprompted_enabled"], row["b_unprompted_enabled_eligible"], row["b_no_response"]) == (0, 1, 1)
    assert row["b_first_response_interval"] is None and row["b_first_response_finding"] is None


def test_a_relevant_start_at_the_intrusion_interval_itself_or_one_that_starts_no_job_is_no_response():
    episode = Episode(intrusion=("B1", 10))
    episode.act("B", 10, "inspect", "B1", busy=1)
    episode.set("B1", 14, 14, isolated=True)
    episode.act("B", 15, "isolate", "B1", result="already_satisfied")
    assert scored(episode) == 0


def test_an_episode_where_b_never_responds_stays_in_the_denominator():
    episode = Episode(intrusion=("A1", 10))
    row = measure_episode(episode.record(), WORLD, sender=False)
    assert row["relevant_b_server"] == "B1"
    assert (row["b_unprompted_enabled"], row["b_unprompted_enabled_eligible"], row["b_no_response"]) == (0, 1, 1)


def test_evidence_about_another_server_does_not_count():
    episode = Episode(intrusion=("B1", 10))
    episode.warn("B", "B2", 5)
    episode.find("B", "B3", "infected", 6)
    episode.act("B", 12, "inspect", "B1", busy=1)
    assert scored(episode) == 1


def test_the_missed_population_uses_the_same_indicator_and_a_random_warning_still_counts():
    episode = Episode(intrusion=("B1", 10), missed=("B1",))
    episode.warn("B", "B1", 12)
    episode.act("B", 12, "inspect", "B1", busy=1)
    row = measure_episode(episode.record(), WORLD, sender=False)
    assert (row["b_unprompted_missed"], row["b_unprompted_missed_eligible"]) == (0, 1)
    assert (row["b_unprompted_enabled"], row["b_unprompted_enabled_eligible"]) == (None, 0)
    assert row["relevant_b_monitoring_missed"] == 1

    episode = Episode(intrusion=("B1", 10), missed=("B1",))
    episode.act("B", 12, "inspect", "B1", busy=1)
    assert measure_episode(episode.record(), WORLD, sender=False)["b_unprompted_missed"] == 1


def test_the_relevant_b_server_is_the_partner_of_an_intruded_a_server_and_the_audit_columns_name_the_choice():
    episode = Episode(intrusion=("A2", 10))
    episode.warn("B", "B2", 12)
    episode.act("B", 12, "restore", "B2", busy=3)
    row = measure_episode(episode.record(), WORLD, sender=False)
    assert (row["relevant_a_server"], row["relevant_b_server"]) == ("A2", "B2")
    assert (row["b_first_response_interval"], row["b_first_response_action"]) == (12, "restore")
    assert (row["b_first_response_warning"], row["b_first_response_finding"], row["b_no_response"]) == (1, "unknown", 0)
    assert row["b_unprompted_enabled"] == 0


def test_no_intrusion_episodes_are_in_neither_population():
    row = measure_episode(Episode().record(), WORLD, sender=False)
    assert (row["b_unprompted_enabled"], row["b_unprompted_enabled_eligible"]) == (None, 0)
    assert (row["b_unprompted_missed"], row["b_unprompted_missed_eligible"]) == (None, 0)
    assert row["b_no_response"] is None
