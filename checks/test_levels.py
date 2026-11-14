import pytest

from measurements.arm import (
    arm_columns,
    arm_learning_curve,
    arm_summary,
    arm_training_behaviour,
    learning_curve_columns,
    summary,
    training_behaviour_columns,
)
from measurements.glossary import measurement_rows
from measurements.study import (
    master_ids,
    master_table,
    sender_studies_summary,
    sender_summary_columns,
)
from measurements.tables import read_csv, write_csv
from measurements.training_series import SERIES
from measurements.world import probe_ids, world_columns, world_table

CONTROLS = ["cue-hidden-unknown-at-evaluation", "cue-hidden-failures-suppressed-at-evaluation"]


def cell(value):
    return "" if value is None else str(value)


def team(values: dict) -> list[dict]:
    rows = []
    for id, (value, numerator, denominator) in values.items():
        rows.append({"id": id, "value": cell(value), "numerator": cell(numerator), "denominator": cell(denominator)})
    return rows


def through_csv(tmp_path, rows, columns):
    write_csv(tmp_path / "file.csv", rows, columns)
    return read_csv(tmp_path / "file.csv")


def test_a_mean_is_over_the_defined_teams_only():
    assert summary([1.0, None, 3.0]) == {"mean": 2.0, "sd": pytest.approx(2 ** 0.5), "minimum": 1.0,
                                         "maximum": 3.0, "teams": 2}
    assert summary([None, 4.0, None]) == {"mean": 4.0, "sd": None, "minimum": 4.0, "maximum": 4.0, "teams": 1}
    assert summary([None, None]) == {"mean": None, "sd": None, "minimum": None, "maximum": None, "teams": 0}
    assert summary([0.0, 0.0])["mean"] == 0.0


def test_the_arm_summary_lists_every_team_and_its_controls():
    teams = {0: team({"reward": (-40.0, -80.0, 2), "a_interrupt_relevant": (0.01, 1.0, 100)}),
             1: team({"reward": (-30.0, -60.0, 2), "a_interrupt_relevant": (0.009, 0.9, 100)}),
             2: team({"reward": (-20.0, -40.0, 2), "a_interrupt_relevant": (None, 0.0, 0)})}
    controls = {}
    for control in CONTROLS:
        controls[control] = {}
        for seed in (0, 1, 2):
            controls[control][seed] = team({"reward": (-50.0, -100.0, 2), "ctrl_reward": (seed + 1.0, 2.0, 2)})

    rows = arm_summary(teams, controls, sender=True)
    assert [(row["id"], row["control"]) for row in rows] == [("reward", ""), ("a_interrupt_relevant", ""),
                                                             ("ctrl_reward", CONTROLS[0]), ("ctrl_reward", CONTROLS[1])]
    reward, relevant, ctrl, _ = rows
    assert (reward["seed0"], reward["seed1"], reward["seed2"], reward["mean"], reward["teams"]) == (-40.0, -30.0, -20.0, -30.0, 3)
    assert reward["sd"] == pytest.approx(10.0)
    assert relevant["teams_at_or_above_1_percent"] == 1
    assert relevant["teams"] == 2
    assert reward["teams_at_or_above_1_percent"] is None
    assert ctrl["mean"] == 2.0
    assert set(rows[0]) == set(arm_columns([0, 1, 2], True))

    teams[2] = team({"a_interrupt_relevant": (0.5, 50.0, 100), "reward": (-20.0, -40.0, 2)})
    with pytest.raises(ValueError, match="other measurements"):
        arm_summary(teams, {}, sender=True)


def test_the_arm_learning_curve_and_training_behaviour_are_per_iteration_and_block():
    curves = {0: [{"iteration": "1", "mean_reward": "-10"}, {"iteration": "2", "mean_reward": "-8"}],
              1: [{"iteration": "1", "mean_reward": "-14"}, {"iteration": "2", "mean_reward": "-6"}]}
    rows = arm_learning_curve(curves)
    assert [(row["iteration"], row["mean"], row["teams"]) for row in rows] == [(1, -12.0, 2), (2, -7.0, 2)]
    assert rows[0]["sd"] == pytest.approx(8 ** 0.5)
    assert set(rows[0]) == set(learning_curve_columns([0, 1]))
    curves[1] = curves[1][:1]
    with pytest.raises(ValueError, match="other training iterations"):
        arm_learning_curve(curves)

    def block(value):
        row = {"block": "1", "first_iteration": "1", "last_iteration": "100"}
        for id in SERIES:
            row[id] = cell(value)
        return [row]

    rows = arm_training_behaviour({0: block(0.2), 1: block(None), 2: block(0.4)})
    assert rows[0]["b_responds_to_a_mean"] == pytest.approx(0.3)
    assert rows[0]["b_responds_to_a_teams"] == 2
    assert set(rows[0]) == set(training_behaviour_columns())


def sender_world(tmp_path):
    arms = {"cue-visible": {}, "cue-hidden-failures-suppressed": {}}
    values = {("cue-visible", 0): (-30.0, 0.02, 0.6), ("cue-visible", 1): (-34.0, 0.004, None),
              ("cue-hidden-failures-suppressed", 0): (-40.0, 0.03, 0.2),
              ("cue-hidden-failures-suppressed", 1): (-44.0, None, 0.1)}
    teams = {}
    for (arm, seed), (reward, relevant, probe) in values.items():
        measured = {"reward": (reward, reward * 2, 2), "a_interrupt_relevant": (relevant, 1.0, 50),
                    "before_reward": (reward - 10, (reward - 10) * 2, 2), "b_responds_to_a": (0.8, 8.0, 10)}
        for id in probe_ids(True):
            measured[id] = (probe, 3.0, 5)
        teams[(arm, seed)] = team(measured)
        arms[arm][seed] = teams[(arm, seed)]
    responses = {CONTROLS[0]: ((None, 0.0, 0), (None, None, None)), CONTROLS[1]: ((0.25, 1.0, 4), (0.55, None, None))}
    controls = {}
    for control in CONTROLS:
        for seed in (0, 1):
            control_rate, difference = responses[control]
            controls[(control, seed)] = team({"reward": (-50.0, -100.0, 2), "b_responds_to_a": control_rate,
                                              "ctrl_reward": (seed + 1.0, 2.0, 2), "ctrl_b_responds_to_a": difference})
    summaries = {}
    for arm, arm_teams in arms.items():
        arm_controls = {}
        if arm == "cue-visible":
            for control in CONTROLS:
                arm_controls[control] = {0: controls[(control, 0)], 1: controls[(control, 1)]}
        summaries[arm] = through_csv(tmp_path, arm_summary(arm_teams, arm_controls, True), arm_columns([0, 1], True))
    baselines = []
    for rule, reward in (("always-wait", -60.0), ("inspect-teacher", -35.0), ("restore-teacher", -45.0),
                         ("random", -400.0)):
        baselines.append((rule, "", None, team({"reward": (reward, reward * 2, 2), "a_interrupt_relevant": (0.0, 0.0, 50)})))
    for arm in arms:
        for seed, reward in ((0, -20.0), (1, -24.0)):
            baselines.append(("a-waits-with-fixed-b", arm, seed, team({"reward": (reward, reward * 2, 2)})))
    rows = world_table(summaries, teams, baselines, controls, sender=True)
    return summaries, through_csv(tmp_path, rows, world_columns(CONTROLS, True))


def test_the_world_table_holds_teams_baselines_means_and_the_arm_difference(tmp_path):
    _, rows = sender_world(tmp_path)
    assert set(rows[0]) == set(world_columns(CONTROLS, True))
    kinds = []
    for row in rows:
        kinds.append((row["row"], row["arm"], row["seed"], row["baseline"]))
    assert kinds == [("team", "cue-visible", "0", ""), ("team", "cue-visible", "1", ""),
                     ("team", "cue-hidden-failures-suppressed", "0", ""), ("team", "cue-hidden-failures-suppressed", "1", ""),
                     ("baseline", "", "", "always-wait"), ("baseline", "", "", "inspect-teacher"),
                     ("baseline", "", "", "restore-teacher"), ("baseline", "", "", "random"),
                     ("baseline", "cue-visible", "0", "a-waits-with-fixed-b"),
                     ("baseline", "cue-visible", "1", "a-waits-with-fixed-b"),
                     ("baseline", "cue-hidden-failures-suppressed", "0", "a-waits-with-fixed-b"),
                     ("baseline", "cue-hidden-failures-suppressed", "1", "a-waits-with-fixed-b"),
                     ("baseline mean", "cue-visible", "", "a-waits-with-fixed-b"),
                     ("baseline mean", "cue-hidden-failures-suppressed", "", "a-waits-with-fixed-b"),
                     ("arm mean", "cue-visible", "", ""), ("arm mean", "cue-hidden-failures-suppressed", "", ""),
                     ("arm difference", "", "", "")]
    first = rows[0]
    assert (first["reward"], first["reward_numerator"], first["reward_denominator"]) == ("-30.0", "-60.0", "2")
    assert (first["below_1_percent"], rows[1]["below_1_percent"], rows[3]["below_1_percent"]) == ("0", "1", "")
    assert first[f"ctrl_reward__{CONTROLS[0]}"] == "1.0"
    assert rows[1][f"ctrl_reward__{CONTROLS[1]}_denominator"] == "2"
    assert rows[2][f"ctrl_reward__{CONTROLS[0]}"] == ""
    responses = []
    for control in CONTROLS:
        responses.append((first[f"b_responds_to_a__{control}"], first[f"b_responds_to_a__{control}_numerator"],
                          first[f"b_responds_to_a__{control}_denominator"], first[f"ctrl_b_responds_to_a__{control}"],
                          first[f"ctrl_b_responds_to_a__{control}_denominator"]))
    assert (first["b_responds_to_a"], first["b_responds_to_a_numerator"], first["b_responds_to_a_denominator"]) == (
        "0.8", "8.0", "10")
    assert responses == [("", "0.0", "0", "", ""), ("0.25", "1.0", "4", "0.55", "")]
    assert rows[2][f"b_responds_to_a__{CONTROLS[1]}"] == ""
    assert float(first["probe_interrupt_warning__arm_difference"]) == pytest.approx(0.4)
    assert rows[1]["probe_interrupt_warning__arm_difference"] == ""
    assert rows[2]["probe_interrupt_warning__arm_difference"] == ""
    assert rows[4]["probe_interrupt_warning"] == "" and rows[4]["before_reward"] == ""
    assert float(rows[12]["reward"]) == -22.0
    assert float(rows[14]["reward"]) == -32.0 and float(rows[15]["reward"]) == -42.0
    assert float(rows[14][f"ctrl_reward__{CONTROLS[0]}"]) == 1.5
    assert rows[14]["reward_numerator"] == "" and rows[14]["reward_denominator"] == ""
    assert float(rows[16]["reward"]) == 10.0
    assert float(rows[15]["a_interrupt_relevant"]) == 0.03


def test_the_world_table_refuses_a_measurement_it_has_no_column_for(tmp_path):
    summaries, _ = sender_world(tmp_path)
    with pytest.raises(ValueError, match="no column for"):
        world_table(summaries, {("cue-visible", 0): team({"rewards": (1.0, 1.0, 1)})}, [], {}, sender=True)


def receiver_arm(values: dict) -> dict:
    rows = {}
    for row in measurement_rows(False):
        if not row["id"].startswith("ctrl_"):
            rows[row["id"]] = (values.get(row["id"], 1.0), 1.0, 1)
    return rows


def test_the_master_table_copies_the_arm_means_baselines_and_controls(tmp_path):
    arms = {"cue-visible": {}, "cue-hidden-unknown": {}}
    teams = {}
    for arm, rewards, eligible in (("cue-visible", (-30.0, -34.0), (12, 8)), ("cue-hidden-unknown", (-40.0, -44.0), (0, 0))):
        for seed in (0, 1):
            values = receiver_arm({"reward": rewards[seed]})
            values["b_acts_on_peer_failure"] = (None if eligible[seed] == 0 else 0.5, 0.0, eligible[seed])
            teams[(arm, seed)] = team(values)
            arms[arm][seed] = teams[(arm, seed)]
    controls = {}
    for control in CONTROLS:
        for seed in (0, 1):
            controls[(control, seed)] = team({"ctrl_reward": (seed + 1.0, 2.0, 2), "ctrl_b_infected_end": (0.0, 0.0, 2)})
    summaries = {}
    for arm, arm_teams in arms.items():
        arm_controls = {}
        if arm == "cue-visible":
            for control in CONTROLS:
                arm_controls[control] = {0: controls[(control, 0)], 1: controls[(control, 1)]}
        summaries[arm] = through_csv(tmp_path, arm_summary(arm_teams, arm_controls, False), arm_columns([0, 1], False))
    baselines = []
    for rule, reward in (("always-wait", -60.0), ("inspect-teacher", -35.0), ("restore-teacher", -45.0), ("random", -400.0)):
        baselines.append((rule, "", None, team(receiver_arm({"reward": reward}))))
    world_rows = through_csv(tmp_path, world_table(summaries, teams, baselines, controls, False), world_columns(CONTROLS, False))

    rows = master_table({"reliable-warnings": (summaries, world_rows)}, False)
    row = rows[0]
    assert row["world"] == "reliable-warnings"
    assert float(row["reward__cue-visible__mean"]) == -32.0
    assert row["reward__cue-visible__teams"] == "2"
    assert float(row["reward__arm_difference"]) == 10.0
    assert row["b_acts_on_peer_failure__cue-visible__eligible"] == 20
    assert row["b_acts_on_peer_failure__cue-hidden-unknown__eligible"] == 0
    assert row["b_acts_on_peer_failure__cue-hidden-unknown__mean"] == ""
    assert row["b_acts_on_peer_failure__cue-hidden-unknown__teams"] == "0"
    assert float(row["reward__inspect-teacher"]) == -35.0
    assert "reward__random" not in row
    assert float(row[f"ctrl_reward__{CONTROLS[1]}__mean"]) == 1.5
    for id in master_ids(False):
        assert f"{id}__cue-hidden-unknown__mean" in row


def test_the_sender_summary_copies_the_master_tables():
    row = {"world": "reliable-warnings"}
    for arm in ("cue-visible", "cue-hidden-failures-suppressed"):
        for id, mean in (("a_interrupt_relevant", 0.02), ("a_interrupt_on_evidence_infected", 0.5),
                         ("b_responds_to_a", 0.25), ("reward", -30.0)):
            row[f"{id}__{arm}__mean"] = str(mean)
            row[f"{id}__{arm}__teams"] = "5"
        row[f"a_interrupt_relevant__{arm}__teams_at_or_above_1_percent"] = "3"
    rows = sender_studies_summary({"study-3-sender-random-a-fixed-b": ([row], ["cue-visible", "cue-hidden-failures-suppressed"])})
    assert len(rows) == 2
    assert set(rows[0]) == set(sender_summary_columns())
    assert rows[0] == {"study": "study-3-sender-random-a-fixed-b", "world": "reliable-warnings", "arm": "cue-visible",
                       "a_interrupt_relevant_mean": "0.02", "a_interrupt_relevant_teams": "5",
                       "teams_at_or_above_1_percent": "3", "a_interrupt_on_evidence_infected_mean": "0.5",
                       "a_interrupt_on_evidence_infected_teams": "5", "b_responds_to_a_mean": "0.25",
                       "b_responds_to_a_teams": "5", "reward_mean": "-30.0", "reward_teams": "5"}
