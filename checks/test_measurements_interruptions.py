import pytest

from checks.record_builder import WORLD, Episode, pick
from measurements.episode import measure_episode
from measurements.interruptions import interruptions_of


def a_restores_a1_at_14(**masks):

    episode = Episode(intrusion=("A1", 10), **masks)
    episode.act("A", 14, "restore", "A1", busy=3)
    episode.set("A1", 14, isolated=True, service_running=False)
    episode.complete("A", 17, "restore")
    episode.set("A1", 17, isolated=True, service_running=True)
    return episode


def only(rows):
    assert len(rows) == 1
    return rows[0]


def test_a_restore_of_a_running_connected_server_is_an_interruption_and_b_sees_the_failure_next():
    row = only(interruptions_of(a_restores_a1_at_14().record(), WORLD))
    assert (row["interval"], row["target"], row["action"], row["target_compromised_at_start"]) == (14, "A1", "restore", 1)
    assert (row["paired_b_server"], row["observable"], row["b_shown_failure"], row["relevant"]) == ("B1", 1, 1, 1)


def test_a_restore_of_an_isolated_or_stopped_server_is_a_start_but_not_an_interruption():
    for flags in ({"isolated": True}, {"service_running": False}):
        episode = Episode()
        episode.set("A2", 5, 5, **flags)
        episode.act("A", 6, "restore", "A2", busy=3)
        episode.set("A2", 6, isolated=True, service_running=False)
        row = measure_episode(episode.record(), WORLD, sender=True)
        assert (row["a_restores"], row["a_interrupts"]) == (1, 0)


def test_an_isolate_of_an_isolated_server_starts_no_job_and_is_not_counted():
    episode = Episode()
    episode.set("A2", 5, isolated=True)
    episode.act("A", 8, "isolate", "A2", result="already_satisfied")
    row = measure_episode(episode.record(), WORLD, sender=True)
    assert (row["a_isolates"], row["a_interrupts"]) == (0, 0)


def test_an_interruption_is_not_observable_when_b_starts_a_restore_of_the_paired_server_in_the_same_interval():
    episode = Episode()
    episode.act("A", 14, "isolate", "A2")
    episode.set("A2", 14, isolated=True)
    episode.act("B", 14, "restore", "B2", busy=3)
    episode.set("B2", 14, isolated=True, service_running=False)
    row = only(interruptions_of(episode.record(), WORLD))
    assert (row["paired_b_running_at_requests"], row["paired_b_isolated_at_requests"], row["observable"]) == (0, 1, 0)


def test_an_interruption_is_observable_when_b_completes_a_reconnect_of_the_paired_server_in_the_same_interval():
    episode = Episode()
    episode.set("B2", 10, 13, isolated=True)
    episode.act("B", 14, "reconnect", "B2")
    episode.complete("B", 14, "reconnect")
    episode.act("A", 14, "isolate", "A2")
    episode.set("A2", 14, isolated=True)
    row = only(interruptions_of(episode.record(), WORLD))
    assert (row["paired_b_running_at_requests"], row["paired_b_isolated_at_requests"], row["observable"]) == (1, 0, 1)


def test_relevant_means_the_relevant_a_server_strictly_after_the_intrusion_interval():
    episode = Episode(intrusion=("B2", 10))
    episode.act("A", 10, "isolate", "A2")
    episode.set("A2", 10, 11, isolated=True)
    episode.act("A", 12, "isolate", "A1")
    episode.set("A1", 12, 13, isolated=True)
    row = measure_episode(episode.record(), WORLD, sender=True)
    assert (row["a_interrupts"], row["a_interrupt_relevant"], row["a_interrupt_relevant_eligible"]) == (2, 0, 1)

    episode.act("A", 14, "isolate", "A2")
    episode.set("A2", 14, isolated=True)
    row = measure_episode(episode.record(), WORLD, sender=True)
    assert (row["a_interrupts"], row["a_interrupt_relevant"]) == (3, 1)


def test_a_no_intrusion_episode_is_outside_the_relevant_measurements():
    episode = Episode()
    episode.act("A", 14, "isolate", "A2")
    episode.set("A2", 14, isolated=True)
    row = measure_episode(episode.record(), WORLD, sender=True)
    assert (row["a_interrupts"], row["a_interrupts_eligible"]) == (1, 1)
    for id in ("a_interrupt_relevant", "a_interrupt_relevant_b_closed", "a_interrupt_b_unaware", "a_infected_intervals"):
        assert (row[id], row[f"{id}_eligible"]) == (None, 0)
    assert only(interruptions_of(episode.record(), WORLD))["relevant"] == 0


@pytest.mark.parametrize("closed, expected", [("none", 0), ("compromised", 1), ("patched", 1)])
def test_the_first_relevant_interruption_finds_the_paired_b_server_already_infected_or_patched(closed, expected):
    episode = a_restores_a1_at_14()
    if closed == "compromised":
        episode.spread("A1", 11)
    if closed == "patched":
        episode.act("B", 5, "restore", "B1", busy=3)
        episode.set("B1", 5, 7, isolated=True, service_running=False)
        episode.complete("B", 8, "restore")
    row = measure_episode(episode.record(), WORLD, sender=True)
    assert (row["a_interrupt_relevant_b_closed"], row["a_interrupt_relevant_b_closed_eligible"]) == (expected, 1)
    interruption = only(interruptions_of(episode.record(), WORLD))
    assert interruption["paired_b_compromised_at_start"] == int(closed == "compromised")
    assert interruption["paired_b_patched_at_start"] == int(closed == "patched")


def test_the_paired_b_server_s_status_at_start_includes_an_intrusion_of_that_same_interval():
    episode = Episode(intrusion=("B2", 10))
    episode.act("A", 10, "isolate", "A2")
    episode.set("A2", 10, isolated=True)
    row = only(interruptions_of(episode.record(), WORLD))
    assert (row["paired_b_compromised_at_start"], row["relevant"]) == (1, 0)


def test_clean_interruptions_are_read_from_the_truth_at_job_start():
    episode = Episode(intrusion=("A1", 10))
    episode.act("A", 5, "isolate", "A1")
    episode.set("A1", 5, 9, isolated=True)
    episode.act("A", 12, "isolate", "A1")
    episode.set("A1", 12, isolated=True)
    row = measure_episode(episode.record(), WORLD, sender=True)
    assert (row["a_interrupts"], row["a_interrupts_clean"]) == (2, 1)


def test_b_unaware_reads_b_s_observation_after_the_first_observable_relevant_interruption():
    episode = Episode(intrusion=("A1", 10))
    episode.act("A", 12, "isolate", "A1")
    episode.set("A1", 12, 13, isolated=True)
    episode.set("B1", 12, 12, service_running=False)
    episode.act("A", 16, "isolate", "A1")
    episode.set("A1", 16, isolated=True)
    episode.warn("B", "B1", 13, 13)
    rows = interruptions_of(episode.record(), WORLD)
    assert pick(rows, "interval", "observable") == [(12, 0), (16, 1)]
    row = measure_episode(episode.record(), WORLD, sender=True)
    assert (row["a_interrupt_b_unaware"], row["a_interrupt_b_unaware_eligible"]) == (1, 1)

    episode.warn("B", "B1", 17, 17)
    assert measure_episode(episode.record(), WORLD, sender=True)["a_interrupt_b_unaware"] == 0


def test_no_observable_relevant_interruption_leaves_b_unaware_undefined():
    episode = a_restores_a1_at_14()
    episode.set("B1", 14, 14, isolated=True)
    row = measure_episode(episode.record(), WORLD, sender=True)
    assert (row["a_interrupt_b_unaware"], row["a_interrupt_b_unaware_eligible"]) == (None, 0)


def test_study_1_rows_leave_every_sender_column_empty():
    row = measure_episode(a_restores_a1_at_14().record(), WORLD, sender=False)
    for id in ("a_restores", "a_interrupts", "a_interrupt_relevant", "a_infected_intervals"):
        assert row[id] is None and row[f"{id}_eligible"] is None


def response(episode):
    row = only(interruptions_of(episode.record(), WORLD))
    assert row["relevant"] == 1 and row["interval"] == 14
    return row


@pytest.mark.parametrize("action", ["inspect", "isolate", "restore"])
def test_b_free_at_15_acts_on_the_running_connected_paired_server(action):
    episode = a_restores_a1_at_14()
    episode.act("B", 15, action, "B1")
    row = response(episode)
    assert (row["b_choice_boundary"], row["delay"], row["b_responds_eligible"], row["b_responds"]) == (15, 0, 1, 1)


@pytest.mark.parametrize("action, target", [("wait", None), ("inspect", "B2"), ("restore", "B3")])
def test_b_free_at_15_waits_or_acts_on_another_server(action, target):
    episode = a_restores_a1_at_14()
    episode.act("B", 15, action, target)
    row = response(episode)
    assert (row["b_responds_eligible"], row["b_responds"]) == (1, 0)


def test_b_busy_at_15_and_16_restores_the_paired_server_at_17_while_a1_is_still_isolated():
    episode = a_restores_a1_at_14()
    episode.act("B", 14, "inspect", "B3", busy=2)
    episode.act("B", 17, "restore", "B1", busy=3)
    row = response(episode)
    assert (row["b_choice_boundary"], row["delay"], row["b_responds_eligible"], row["b_responds"]) == (17, 2, 1, 1)


def test_a_reconnects_a1_during_16_so_the_window_ends_at_16_with_no_free_choice_of_b():
    episode = Episode(intrusion=("A1", 10))
    episode.act("A", 14, "isolate", "A1")
    episode.set("A1", 14, 15, isolated=True)
    episode.act("A", 16, "reconnect", "A1")
    episode.complete("A", 16, "reconnect")
    episode.act("B", 14, "inspect", "B3", busy=2)
    episode.act("B", 17, "restore", "B1", busy=3)
    row = response(episode)
    assert (row["window_last_boundary"], row["b_choice_boundary"]) == (16, None)
    assert (row["b_responds_eligible"], row["b_responds"]) == (0, None)


def test_b_free_at_15_with_the_paired_server_isolated_in_its_observation_reconnects_it():
    episode = a_restores_a1_at_14()
    episode.set("B1", 13, 14, isolated=True)
    episode.act("B", 15, "reconnect", "B1")
    row = response(episode)
    assert (row["b_choice_boundary"], row["paired_b_available_at_choice"]) == (15, 0)
    assert (row["b_responds_eligible"], row["b_responds"]) == (0, None)


def test_b_restores_the_paired_server_with_its_own_warning_visible_and_the_audit_column_says_so():
    episode = a_restores_a1_at_14()
    episode.warn("B", "B1", 15)
    episode.act("B", 15, "restore", "B1", busy=3)
    row = response(episode)
    assert (row["b_responds_eligible"], row["b_responds"], row["paired_b_warning_at_choice"]) == (1, 1, 1)


@pytest.mark.parametrize("masks", [{"suppress": ("B",)}, {"hide": ("B",)}])
def test_under_a_mask_b_sees_no_failure_waits_and_the_interruption_still_counts(masks):
    episode = a_restores_a1_at_14(**masks)
    row = response(episode)
    assert (row["b_shown_failure"], row["observable"], row["b_responds_eligible"], row["b_responds"]) == (0, 1, 1, 0)


def test_a_later_interruption_of_the_same_server_opens_a_window_of_its_own():
    episode = Episode(intrusion=("A1", 10))
    episode.act("A", 14, "isolate", "A1")
    episode.set("A1", 14, 15, isolated=True)
    episode.act("A", 16, "reconnect", "A1")
    episode.act("A", 20, "isolate", "A1")
    episode.set("A1", 20, isolated=True)
    episode.act("B", 21, "inspect", "B1", busy=1)
    rows = interruptions_of(episode.record(), WORLD)
    assert pick(rows, "interval", "window_last_boundary", "b_choice_boundary", "b_responds") == [
        (14, 16, 15, 0), (20, 49, 21, 1)]


def test_an_interruption_in_the_last_interval_has_an_empty_window():
    episode = Episode(intrusion=("A1", 10))
    episode.act("A", 49, "isolate", "A1")
    episode.set("A1", 49, isolated=True)
    row = response_at(episode, 49)
    assert (row["window_last_boundary"], row["b_choice_boundary"], row["b_responds_eligible"]) == (None, None, 0)


def response_at(episode, interval):
    for row in interruptions_of(episode.record(), WORLD):
        if row["interval"] == interval:
            return row
    raise AssertionError(f"no interruption at {interval}")


def test_episodes_csv_carries_each_episode_s_b_responds_to_a_counts_and_study_1_leaves_them_empty():
    episode = Episode(intrusion=("A1", 10))
    episode.act("A", 14, "isolate", "A1")
    episode.set("A1", 14, 15, isolated=True)
    episode.act("A", 16, "reconnect", "A1")
    episode.act("B", 15, "restore", "B1", busy=3)
    episode.act("A", 25, "isolate", "A1")
    episode.set("A1", 25, isolated=True)
    episode.act("A", 30, "isolate", "A2")
    episode.set("A2", 30, isolated=True)
    row = measure_episode(episode.record(), WORLD, sender=True)
    assert (row["b_responds_to_a_numerator"], row["b_responds_to_a_denominator"]) == (1, 2)
    row = measure_episode(episode.record(), WORLD, sender=False)
    assert (row["b_responds_to_a_numerator"], row["b_responds_to_a_denominator"]) == (None, None)
    assert (row["b_acts_on_peer_failure_numerator"], row["b_acts_on_peer_failure_denominator"]) == (1, 25)
