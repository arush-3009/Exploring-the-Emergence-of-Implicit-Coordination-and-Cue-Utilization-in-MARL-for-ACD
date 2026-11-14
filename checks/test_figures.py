import csv
import html
import re

from figures import study_figures, world_figures
from figures.style import BASELINES, FIGURE_COLUMNS
from measurements.glossary import measurement_rows
from measurements.tables import read_csv
from studies.definitions import A_WAITS_BASELINE, SMOKE, STUDIES
from studies.paths import arm_folder, roots, world_folder
from studies.plan import smoke_study

PUBLIC, _ = roots(True)

IDS = {}
for _sender in (False, True):
    for _row in measurement_rows(_sender):
        IDS[_row["plain_name"]] = _row["id"]

BASELINE_NAMES = {}
for _rule, (_label, _, _) in BASELINES.items():
    BASELINE_NAMES[_label] = _rule


def world_inputs(smoke_run, study):
    world = smoke_run / PUBLIC / world_folder(study, SMOKE["world"])
    summaries = {}
    for arm in study.arms:
        summaries[arm] = read_csv(smoke_run / PUBLIC / arm_folder(study, SMOKE["world"], arm) / "arm_summary.csv")
    return world, read_csv(world / "world_table.csv"), summaries


def table_row(table, kind, arm, seed, baseline=""):
    found = []
    for row in table:
        if row["row"] == kind and row["arm"] == arm and row["seed"] == seed and row["baseline"] == baseline:
            found.append(row)
    assert len(found) == 1
    return found[0]


def summary_row(summary, id, control):
    for row in summary:
        if row["id"] == id and row["control"] == control:
            return row
    raise AssertionError(f"no arm summary row {id} {control}")


def test_every_point_of_the_world_figures_is_a_value_of_the_tables(smoke_run):
    checked = {}
    for study in STUDIES.values():
        study = smoke_study(study)
        world, table, summaries = world_inputs(smoke_run, study)
        controlled = next(iter(study.arms))

        for name in ("W1-performance", "W2-signalling" if study.kind == "sender" else "W2-behaviour", "W3-controls"):
            with (world / "figures" / f"{name}.csv").open(newline="") as file:
                reader = csv.DictReader(file)
                assert reader.fieldnames == FIGURE_COLUMNS
                rows = list(reader)

            teams = {}
            for row in rows:
                if row["mark"] == "zoom":
                    continue
                id = IDS[row["panel"]]
                arm, column, control = row["series"], id, ""
                if id.startswith("ctrl_"):
                    arm, column, control = controlled, f"{id}__{row['series']}", row["series"]

                if row["mark"] in ("team", "undefined"):
                    source = table_row(table, "team", arm, row["seed"])
                    cell = source[column]
                    assert row["value"] == cell
                    assert (cell == "") == (row["mark"] == "undefined")
                    teams[(row["panel"], row["series"])] = teams.get((row["panel"], row["series"]), 0) + 1
                    if row["count"] != "":
                        assert (row["numerator"], row["count"]) == (source[f"{column}_numerator"],
                                                                    source[f"{column}_denominator"])
                    if id == "ctrl_b_responds_to_a":
                        assert (row["numerator"], row["count"]) == ("", "")
                elif row["mark"] in ("normal", "control"):
                    source = table_row(table, "team", controlled, row["seed"])
                    rate = "b_responds_to_a" if row["mark"] == "normal" else f"b_responds_to_a__{row['series']}"
                    assert (row["value"], row["numerator"], row["count"]) == (
                        source[rate], source[f"{rate}_numerator"], source[f"{rate}_denominator"])
                elif row["mark"] == "before":
                    assert row["value"] == table_row(table, "team", arm, row["seed"])[f"before_{id}"] != ""
                elif row["mark"] == "a-waits":
                    assert row["value"] == table_row(table, "baseline", arm, row["seed"], A_WAITS_BASELINE)[id] != ""
                elif row["mark"] == "mean":
                    summary = summary_row(summaries[arm], id, control)
                    assert (row["value"], row["count"]) == (summary["mean"], summary["teams"])
                    assert row["value"] != ""
                elif row["mark"] == "baseline":
                    baseline = table_row(table, "baseline", "", "", BASELINE_NAMES[row["series"]])
                    assert row["value"] == baseline[id] != ""
                else:
                    raise AssertionError(f"{name} has a point marked {row['mark']}")
                checked[row["mark"]] = checked.get(row["mark"], 0) + 1

            for count in teams.values():
                assert count == len(study.seeds)

    assert checked["undefined"] >= 2
    assert checked["normal"] == checked["control"] == 4 * 2 * 2
    assert checked["before"] > 0 and checked["a-waits"] > 0 and checked["baseline"] > 0


def test_every_point_of_the_learning_figure_is_a_value_of_the_arm_files(smoke_run):
    checked = 0
    for study in STUDIES.values():
        study = smoke_study(study)
        world = smoke_run / PUBLIC / world_folder(study, SMOKE["world"])
        curves = {}
        behaviours = {}
        for arm in study.arms:
            folder = smoke_run / PUBLIC / arm_folder(study, SMOKE["world"], arm)
            curves[arm] = {}
            for row in read_csv(folder / "learning_curve.csv"):
                curves[arm][row["iteration"]] = row
            behaviours[arm] = {}
            if study.kind == "sender":
                for row in read_csv(folder / "training_behaviour.csv"):
                    behaviours[arm][row["last_iteration"]] = row

        for row in read_csv(world / "figures" / "W4-learning.csv"):
            if row["mark"] not in ("mean", "undefined"):
                continue
            if row["panel"] == "team reward per training episode":
                source = curves[row["series"]][row["x"]]
                value, sd, teams = source["mean"], source["sd"], source["teams"]
            else:
                id = IDS[row["panel"].removesuffix(", per block of training iterations")]
                source = behaviours[row["series"]][row["x"]]
                value, sd, teams = source[f"{id}_mean"], source[f"{id}_sd"], source[f"{id}_teams"]
            assert (row["value"], row["sd"], row["count"]) == (value, sd, teams)
            assert (row["mark"] == "undefined") == (value == "")
            checked += 1
        for arm in study.arms:
            if study.kind == "sender":
                assert list(behaviours[arm]) == ["3"] and list(curves[arm]) == ["1", "2", "3"]
    assert checked == 5 * 2 * 3 + 4 * 2 * 2


def svg_text(path):
    text = []
    for match in re.finditer(r"<text[^>]*>(.*?)</text>", path.read_text(), re.DOTALL):
        text.append(html.unescape(match.group(1)))
    return text


def test_the_w1_zoom_holds_the_teams_and_names_what_it_leaves_out(smoke_run):
    zooms = 0
    for study in STUDIES.values():
        study = smoke_study(study)
        world = smoke_run / PUBLIC / world_folder(study, SMOKE["world"])
        shown = []
        baselines = {}
        limits = {}
        everything = []
        for row in read_csv(world / "figures" / "W1-performance.csv"):
            if row["mark"] == "zoom":
                limits[row["series"]] = float(row["value"])
            elif row["panel"] == "team reward per episode" and row["value"] != "":
                everything.append(float(row["value"]))
                if row["mark"] in ("team", "before", "a-waits"):
                    shown.append(float(row["value"]))
                elif row["mark"] == "baseline":
                    baselines[row["series"]] = float(row["value"])
        if not limits:
            continue

        zooms += 1
        lower, upper = limits["lower limit"], limits["upper limit"]
        for value in [*shown, baselines["inspect-first teacher"], baselines["restore-on-warning teacher"]]:
            assert lower <= value <= upper
        assert upper - lower < 0.5 * (max(everything) - min(everything))
        text = " ".join(svg_text(world / "figures" / "W1-performance.svg"))
        for label, value in baselines.items():
            assert (f"{label} ({value:.1f})" in text) == (not lower <= value <= upper)
        assert ("outside this view" in text) == any(not lower <= value <= upper for value in baselines.values())
    assert zooms > 0


def control_figure(smoke_run, tmp_path, seeds=(0, 1)):

    study = smoke_study(STUDIES[5])
    _, table, summaries = world_inputs(smoke_run, study)
    controlled = next(iter(study.arms))
    unknown, suppressed = study.controls
    rows = []
    for row in table:
        if row["row"] == "team" and row["arm"] == controlled and row["seed"] == "0":
            row = dict(row, b_responds_to_a="0.8", b_responds_to_a_numerator="8.0", b_responds_to_a_denominator="10")
            row.update({f"b_responds_to_a__{suppressed}": "0.25", f"b_responds_to_a__{suppressed}_numerator": "1.0",
                        f"b_responds_to_a__{suppressed}_denominator": "4", f"ctrl_b_responds_to_a__{suppressed}": "0.55",
                        f"b_responds_to_a__{unknown}": "", f"b_responds_to_a__{unknown}_numerator": "0.0",
                        f"b_responds_to_a__{unknown}_denominator": "0", f"ctrl_b_responds_to_a__{unknown}": ""})
            for seed in seeds:
                rows.append(dict(row, seed=str(seed)))
        elif row["row"] in ("team", "baseline") and row["seed"] not in ("", "0"):
            continue
        elif row["row"] in ("team", "baseline") and row["seed"] == "0":
            for seed in seeds:
                rows.append(dict(row, seed=str(seed)))
        else:
            rows.append(row)
    world_figures.controls(rows, summaries, True, tmp_path)
    return rows, summaries, unknown, suppressed


def test_the_control_figure_shows_both_response_rates_behind_each_difference(smoke_run, tmp_path):
    _, _, unknown, suppressed = control_figure(smoke_run, tmp_path)
    rows = read_csv(tmp_path / "W3-controls.csv")
    seed_zero = {}
    for row in rows:
        if row["panel"] == "normal minus control, B responded to A's interruption" and row["seed"] == "0":
            seed_zero[(row["series"], row["mark"])] = (row["value"], row["numerator"], row["count"])
    assert seed_zero == {(suppressed, "team"): ("0.55", "", ""),
                         (suppressed, "normal"): ("0.8", "8.0", "10"),
                         (suppressed, "control"): ("0.25", "1.0", "4"),
                         (unknown, "undefined"): ("", "", ""),
                         (unknown, "normal"): ("0.8", "8.0", "10"),
                         (unknown, "control"): ("", "0.0", "0")}

    text = svg_text(tmp_path / "W3-controls.svg")
    for cell in ("8/10 = 80.0%", "1/4 = 25.0%", "+55.0 pp", "0/0, undefined", "undefined"):
        assert cell in text
    assert "n=" not in text
    assert "n is the team's denominator under the control" not in " ".join(text)
    points = []
    for item in text:
        if item.endswith(" pp") and item[0] in "-0123456789":
            points.append(item)
    assert len(points) > 4


def test_the_figures_hold_five_teams_per_arm_in_five_worlds(smoke_run, tmp_path):
    table, summaries, _, _ = control_figure(smoke_run, tmp_path, seeds=(0, 1, 2, 3, 4))
    world_figures.performance(table, summaries, True, tmp_path)
    worlds = {}
    for world in STUDIES[5].worlds:
        worlds[world] = (table, summaries)
    study_figures.controls(worlds, True, tmp_path)

    marks = {}
    for name in ("W1-performance", "W3-controls", "S3-controls"):
        for row in read_csv(tmp_path / f"{name}.csv"):
            marks[(name, row["mark"])] = marks.get((name, row["mark"]), 0) + 1
    assert marks[("W3-controls", "normal")] == marks[("W3-controls", "control")] == 2 * 5
    assert marks[("S3-controls", "normal")] == marks[("S3-controls", "control")] == 5 * 2 * 5
    assert marks[("W1-performance", "team")] == 3 * 2 * 5


def test_no_figure_shows_a_code_id(smoke_run):
    figures = 0
    for path in (smoke_run / PUBLIC).rglob("*.svg"):
        text = svg_text(path)
        words = re.findall(r"[A-Za-z0-9]+(?:_[A-Za-z0-9]+)+", " ".join(text))
        assert words == [], (path, words)
        assert text, path
        figures += 1
    assert figures == 4 + 3 + 4 * (5 + 4) + 1


def test_the_same_tables_give_the_same_bytes(smoke_run, tmp_path):
    study = smoke_study(STUDIES[3])
    world, table, summaries = world_inputs(smoke_run, study)
    curves = {}
    behaviours = {}
    for arm in study.arms:
        curves[arm] = read_csv(smoke_run / PUBLIC / arm_folder(study, SMOKE["world"], arm) / "learning_curve.csv")
        behaviours[arm] = read_csv(smoke_run / PUBLIC / arm_folder(study, SMOKE["world"], arm) /
                                   "training_behaviour.csv")

    world_figures.draw_world(table, summaries, curves, behaviours, True, tmp_path / "first")
    world_figures.draw_world(table, summaries, curves, behaviours, True, tmp_path / "second")
    names = []
    for path in sorted((tmp_path / "first").iterdir()):
        names.append(path.name)
        assert path.read_bytes() == (tmp_path / "second" / path.name).read_bytes(), path.name
        assert path.read_bytes() == (world / "figures" / path.name).read_bytes(), path.name
    assert len(names) == 15
