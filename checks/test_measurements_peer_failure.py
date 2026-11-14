import pytest

from checks.record_builder import WORLD, Episode
from measurements.decisions import peer_failure_decisions


def counts(episode):
    return peer_failure_decisions(episode.record(), WORLD)


def a2_down_at_14(**masks):
    episode = Episode(**masks)
    episode.set("A2", 14, 14, isolated=True)
    return episode


def test_a_visible_failure_while_b_is_busy_is_no_decision():
    episode = a2_down_at_14()
    episode.act("B", 13, "inspect", "B3", busy=2)
    assert counts(episode) == (0, 0)


def test_b_free_after_the_failure_has_disappeared_is_no_decision():
    episode = a2_down_at_14()
    episode.act("B", 13, "inspect", "B3", busy=2)
    episode.act("B", 16, "inspect", "B2")
    assert counts(episode) == (0, 0)


@pytest.mark.parametrize("action", ["inspect", "isolate", "restore"])
def test_b_acts_on_the_qualifying_server(action):
    episode = a2_down_at_14()
    episode.act("B", 15, action, "B2")
    assert counts(episode) == (1, 1)


@pytest.mark.parametrize("action, target", [("wait", None), ("inspect", "B1"), ("isolate", "B1"), ("restore", "B1")])
def test_b_waits_or_acts_on_another_server(action, target):
    episode = a2_down_at_14()
    episode.act("B", 15, action, target)
    assert counts(episode) == (1, 0)


@pytest.mark.parametrize("target", ["B1", "B2"])
def test_two_qualifying_servers_count_one_decision(target):
    episode = a2_down_at_14()
    episode.set("A1", 14, 14, isolated=True)
    episode.act("B", 15, "restore", target)
    assert counts(episode) == (1, 1)


def test_the_only_failing_server_is_isolated_and_b_reconnects_it():
    episode = Episode()
    episode.set("B2", 13, 14, isolated=True)
    episode.act("B", 15, "reconnect", "B2")
    assert counts(episode) == (0, 0)


def test_the_only_failing_server_is_stopped_by_a_local_outage():
    episode = Episode()
    episode.set("B2", 14, 14, service_running=False)
    assert counts(episode) == (0, 0)


@pytest.mark.parametrize("action", ["inspect", "restore", "reconnect"])
def test_another_server_qualifies_and_b_acts_on_the_isolated_one(action):
    episode = Episode()
    episode.set("A1", 14, 14, isolated=True)
    episode.set("B2", 14, 14, isolated=True)
    episode.act("B", 15, action, "B2")
    assert counts(episode) == (1, 0)


@pytest.mark.parametrize("action", ["inspect", "isolate", "restore"])
def test_a_remote_benign_outage_still_qualifies(action):
    episode = Episode()
    episode.set("A2", 14, 14, service_running=False)
    episode.act("B", 15, action, "B2")
    assert counts(episode) == (1, 1)


def test_a_chosen_response_that_starts_no_job_does_not_qualify():
    episode = a2_down_at_14()
    episode.act("B", 15, "isolate", "B2", result="rejected")
    assert counts(episode) == (1, 0)


def test_waiting_twice_and_inspecting_at_the_third_choice_is_one_of_three():
    episode = Episode()
    episode.set("A2", 14, 16, isolated=True)
    episode.act("B", 17, "inspect", "B2", busy=1)
    assert counts(episode) == (3, 1)


@pytest.mark.parametrize("masks", [{"hide": ("B",)}, {"suppress": ("B",)}])
def test_both_masks_leave_no_eligible_choice(masks):
    episode = a2_down_at_14(**masks)
    episode.act("B", 15, "inspect", "B2")
    assert counts(episode) == (0, 0)


def test_suppression_keeps_a_failure_on_an_unavailable_local_server_which_is_then_excluded():
    episode = Episode(suppress=("B",))
    episode.set("B2", 14, 14, isolated=True)
    record = episode.record()
    assert record.boundaries[15]["observations"]["B"]["servers"]["B2"]["peer_request_result"] == 0
    assert peer_failure_decisions(record, WORLD) == (0, 0)
