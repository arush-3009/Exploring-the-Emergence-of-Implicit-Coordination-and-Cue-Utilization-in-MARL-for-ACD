from measurements.glossary import (
    DIFFERENCE,
    MEASUREMENT_COLUMNS,
    measurement_rows,
    write_measurements_csv,
)
from measurements.tables import read_csv

EVERY_STUDY = ["reward", "b_infected_intervals", "b_infected_end", "failed_requests", "inspections_a",
               "inspections_b", "b_unprompted_enabled", "b_unprompted_missed", "b_acts_on_peer_failure",
               "clean_restores_b", "clean_restores_a"]
SENDER_ONLY = ["a_restores", "a_isolates", "a_interrupts", "a_interrupt_relevant", "a_interrupt_relevant_b_closed",
               "a_interrupt_on_evidence_infected", "a_interrupt_on_evidence_clean", "a_interrupts_clean",
               "a_interrupt_b_unaware", "b_responds_to_a", "a_infected_intervals",
               "probe_interrupt_warning", "probe_interrupt_infected_finding", "probe_interrupt_clean_finding",
               "probe_interrupt_no_evidence", "probe_greedy_interrupt_warning", "probe_greedy_interrupt_infected_finding",
               "probe_greedy_interrupt_clean_finding", "probe_greedy_interrupt_no_evidence"]
CONTROLS = ["ctrl_reward", "ctrl_b_infected_intervals", "ctrl_b_infected_end", "ctrl_b_unprompted_enabled",
            "ctrl_b_unprompted_missed"]
SENDER_CONTROLS = ["ctrl_a_interrupts", "ctrl_a_interrupt_relevant", "ctrl_b_responds_to_a"]


def ids(rows):
    result = []
    for row in rows:
        result.append(row["id"])
    return result


def test_the_receiver_study_has_the_every_study_rows_and_their_five_controls():
    assert ids(measurement_rows(sender=False)) == EVERY_STUDY + CONTROLS


def test_a_sender_study_adds_its_rows_a_before_row_for_every_base_row_and_three_controls():
    before = []
    for id in EVERY_STUDY + SENDER_ONLY:
        before.append("before_" + id)
    assert ids(measurement_rows(sender=True)) == EVERY_STUDY + SENDER_ONLY + before + CONTROLS + SENDER_CONTROLS


def test_every_row_names_its_base_and_a_control_is_a_difference():
    rows = measurement_rows(sender=True)
    assert len(set(ids(rows))) == len(rows)
    for row in rows:
        if row["id"].startswith(("before_", "ctrl_")):
            assert row["id"].split("_", 1)[1] == row["base_id"]
        else:
            assert row["base_id"] is None
        assert (row["kind"] == DIFFERENCE) == row["id"].startswith("ctrl_")
        for column in ("long_name", "plain_name", "population", "denominator"):
            assert row[column]


def test_measurements_csv_is_the_glossary(tmp_path):
    write_measurements_csv(tmp_path / "measurements.csv", sender=True)
    rows = read_csv(tmp_path / "measurements.csv")
    assert list(rows[0]) == MEASUREMENT_COLUMNS
    assert ids(rows) == ids(measurement_rows(sender=True))
    assert rows[0]["base_id"] == ""
