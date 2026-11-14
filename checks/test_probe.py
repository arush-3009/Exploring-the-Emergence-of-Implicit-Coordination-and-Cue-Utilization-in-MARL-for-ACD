import json

import pytest

from checks.record_builder import WORLD, Episode, pick
from episodes.record import action_labels
from measurements.probe import (
    build_probe_list,
    probe_list_columns,
    probe_measurements,
    situation,
)
from measurements.tables import read_csv, write_csv

SITUATION_COLUMNS = ("A1_situation", "A2_situation", "A3_situation")
QUIET = {"service_running": 1, "isolated": 0, "employee_request_result": 1, "peer_request_result": 1,
         "warning_received": 0, "warning_age": -1, "inspection_finding": -1, "inspection_age": -1}


def server(**fields):
    observed = dict(QUIET)
    observed.update(fields)
    return observed


def test_each_eligible_server_has_one_situation():
    assert situation(server(warning_received=1, inspection_finding=1)) == "warning"
    assert situation(server(inspection_finding=1)) == "infected_finding"
    assert situation(server(inspection_finding=0)) == "clean_finding"
    assert situation(server()) == "none"
    assert situation(server(isolated=1, warning_received=1)) is None
    assert situation(server(service_running=0, warning_received=1)) is None


def test_the_list_keeps_every_distinct_free_a_observation_once_in_source_order():
    quiet = Episode()
    quiet.act("A", 5, "inspect", "A1", busy=2)
    first = quiet.record(episode=0)
    second = quiet.record(episode=7, evaluation_seed=2002)
    list_rows, source_rows = build_probe_list([("before-cue-visible", [first]), ("always-wait", [second])], WORLD)

    assert len(list_rows) == 50 - 2
    assert pick(list_rows, "probe") == list(range(48))
    boundaries = []
    for row in source_rows:
        boundaries.append(row["boundary"])
        assert (row["source"], row["episode"], row["evaluation_seed"], row["occurrences"]) == (
            "before-cue-visible", 0, 2001, 2)
    assert 6 not in boundaries and 7 not in boundaries
    assert json.loads(list_rows[0]["observation"]) == first.boundaries[0]["observations"]["A"]


def test_the_no_evidence_flag_needs_an_eligible_target_and_no_evidence_on_any_of_them():
    episode = Episode()
    episode.warn("A", "A1", 10, 10)
    episode.set("A2", 19, 19, isolated=True)
    episode.find("A", "A3", "clean", 20, 20)
    episode.set("A1", 29, 29, isolated=True)
    episode.set("A2", 29, 29, isolated=True)
    episode.set("A3", 29, 29, isolated=True)
    list_rows, _ = build_probe_list([("random", [episode.record()])], WORLD)
    by_boundary = {}
    for row in list_rows:
        by_boundary[json.loads(row["observation"])["elapsed_steps"]] = row
    assert pick([by_boundary[10]], *SITUATION_COLUMNS) == [("warning", "none", "none")]
    assert by_boundary[10]["no_evidence"] == 0
    assert pick([by_boundary[20]], *SITUATION_COLUMNS) == [("none", None, "clean_finding")]
    assert by_boundary[20]["no_evidence"] == 0
    assert by_boundary[11]["no_evidence"] == 1
    assert pick([by_boundary[30]], *SITUATION_COLUMNS) == [(None, None, None)]
    assert by_boundary[30]["no_evidence"] == 0


def answer(number, probabilities, greedy):
    row = {"probe": number, "greedy": greedy}
    for label in action_labels(WORLD, "A"):
        row[label] = probabilities.get(label, 0.0)
    return row


def through_files(tmp_path, list_rows, answer_rows):
    write_csv(tmp_path / "probe-list.csv", list_rows, probe_list_columns(WORLD))
    write_csv(tmp_path / "probe_answers.csv", answer_rows, ["probe"] + action_labels(WORLD, "A") + ["greedy"])
    rows = probe_measurements(read_csv(tmp_path / "probe-list.csv"), read_csv(tmp_path / "probe_answers.csv"), WORLD)
    values = {}
    for row in rows:
        values[row["id"]] = (row["value"], row["numerator"], row["denominator"])
    return values


def test_two_warnings_and_three_servers_without_evidence(tmp_path):
    two_warnings = {"probe": 0, "observation": "{}", "A1_situation": "warning", "A2_situation": "warning",
                    "A3_situation": None, "no_evidence": 0}
    no_evidence = {"probe": 1, "observation": "{}", "A1_situation": "none", "A2_situation": "none",
                   "A3_situation": "none", "no_evidence": 1}
    answers = [answer(0, {"restore_A1": 0.3, "isolate_A1": 0.1, "restore_A2": 0.2, "wait": 0.4}, "restore_A1"),
               answer(1, {"restore_A1": 0.1, "isolate_A2": 0.05, "restore_A3": 0.05, "wait": 0.8}, "wait")]
    values = through_files(tmp_path, [two_warnings, no_evidence], answers)

    value, numerator, denominator = values["probe_interrupt_warning"]
    assert (round(numerator, 9), denominator, round(value, 9)) == (0.6, 1, 0.6)
    assert values["probe_greedy_interrupt_warning"] == (1.0, 1, 1)
    value, numerator, denominator = values["probe_interrupt_no_evidence"]
    assert (round(numerator, 9), denominator) == (0.2, 1)
    assert values["probe_greedy_interrupt_no_evidence"] == (0.0, 0, 1)
    for name in ("infected_finding", "clean_finding"):
        assert values[f"probe_interrupt_{name}"] == (None, 0.0, 0)
        assert values[f"probe_greedy_interrupt_{name}"] == (None, 0, 0)


def test_finding_cases_and_the_greedy_choice_of_any_eligible_target_without_evidence(tmp_path):
    rows = [{"probe": 0, "observation": "{}", "A1_situation": "infected_finding", "A2_situation": "clean_finding",
             "A3_situation": "none", "no_evidence": 0},
            {"probe": 1, "observation": "{}", "A1_situation": None, "A2_situation": "none",
             "A3_situation": "none", "no_evidence": 1}]
    answers = [answer(0, {"isolate_A1": 0.7, "restore_A2": 0.1, "restore_A3": 0.2}, "isolate_A1"),
               answer(1, {"restore_A1": 0.9, "isolate_A3": 0.1}, "restore_A1")]
    values = through_files(tmp_path, rows, answers)
    assert values["probe_interrupt_infected_finding"] == (0.7, 0.7, 1)
    assert values["probe_greedy_interrupt_infected_finding"] == (1.0, 1, 1)
    assert values["probe_interrupt_clean_finding"] == (0.1, 0.1, 1)
    assert values["probe_greedy_interrupt_clean_finding"] == (0.0, 0, 1)
    assert values["probe_interrupt_no_evidence"] == (0.1, 0.1, 1)
    assert values["probe_greedy_interrupt_no_evidence"] == (0.0, 0, 1)


def test_every_probe_needs_exactly_one_answer(tmp_path):
    rows = [{"probe": 0, "observation": "{}", "A1_situation": "warning", "A2_situation": "none",
             "A3_situation": "none", "no_evidence": 0}]
    with pytest.raises(ValueError, match="exactly one answer"):
        through_files(tmp_path, rows, [answer(1, {}, "wait")])
    with pytest.raises(ValueError, match="two answers"):
        through_files(tmp_path, rows, [answer(0, {}, "wait"), answer(0, {}, "wait")])


def test_evidence_on_several_servers_is_one_case_with_the_probability_summed(tmp_path):
    rows = [{"probe": 0, "observation": "{}", "A1_situation": "warning", "A2_situation": "warning",
             "A3_situation": "clean_finding", "no_evidence": 0},
            {"probe": 1, "observation": "{}", "A1_situation": "warning", "A2_situation": "warning",
             "A3_situation": None, "no_evidence": 0}]
    answers = [answer(0, {"restore_A1": 0.45, "isolate_A2": 0.45, "restore_A3": 0.05, "wait": 0.05}, "restore_A1"),
               answer(1, {"restore_A1": 0.2, "isolate_A2": 0.2, "wait": 0.6}, "wait")]
    values = through_files(tmp_path, rows, answers)
    value, numerator, denominator = values["probe_interrupt_warning"]
    assert (round(numerator, 9), denominator, round(value, 9)) == (1.3, 2, 0.65)
    assert values["probe_greedy_interrupt_warning"] == (0.5, 1, 2)
    value, numerator, denominator = values["probe_interrupt_clean_finding"]
    assert (round(numerator, 9), denominator, round(value, 9)) == (0.05, 1, 0.05)
    assert values["probe_greedy_interrupt_clean_finding"] == (0.0, 0, 1)
    assert values["probe_interrupt_no_evidence"] == (None, 0.0, 0)
    assert values["probe_greedy_interrupt_no_evidence"] == (None, 0, 0)

