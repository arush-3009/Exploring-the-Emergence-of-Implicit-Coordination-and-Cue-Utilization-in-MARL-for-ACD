from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, PercentFormatter

from figures.style import (
    BASELINES,
    SERIES_COLOURS,
    definitions,
    figure_row,
    finish,
    is_share,
    number,
    opening,
    plain_name,
    team_panel,
    wrapped,
)

OUTCOMES = ("reward", "b_infected_intervals", "b_infected_end")

AXIS_LABELS = {"reward": "reward per episode",
               "b_infected_intervals": "infected server-intervals per intrusion episode",
               "b_infected_end": "intrusion episodes ending with B infected"}


RECEIVER_BEHAVIOUR = ("b_unprompted_enabled", "b_acts_on_peer_failure", "clean_restores_b", "b_unprompted_missed")


SIGNALLING = ("a_interrupt_relevant", 
              "a_interrupt_on_evidence_infected",
              "a_interrupt_on_evidence_clean",
              "a_interrupt_b_unaware",
              "b_responds_to_a")


SITUATIONS = ("warning", "infected_finding", "clean_finding", "no_evidence")


SIGNS = {"reward": "above zero: lower reward under the control",
         "b_infected_intervals": "below zero: more infection under the control",
         "a_interrupt_relevant": "above zero: A interrupts the attacked pair's server less under the control",
         "b_responds_to_a": "above zero: B responds less under the control"}


QUESTIONS = {"W1-performance": "How well does each team defend?",
             "W2-behaviour": "Does B act on its partner's request failures?",
             "W2-signalling": "Does A interrupt its servers in ways B can see, and does B respond?",
             "W3-controls": "What does each cue-visible team lose when the cue is removed at evaluation?",
             "W4-learning": "How did training go in each arm?",
             "W5-probe": "Given the same inputs, how likely is each A to interrupt?"}


TEACHERS = ("inspect-teacher", "restore-teacher")

RATE_LINES = ("always-wait", "inspect-teacher", "restore-teacher")

ATTACKED_PAIR = "The attacked pair is the pair of servers the intrusion landed in."


def team_rows(table: list[dict], arm: str) -> list[dict]:
    
    rows = []
    for row in table:
        if row["row"] == "team" and row["arm"] == arm:
            rows.append(row)
            
    return rows



def rule_baselines(table: list[dict]) -> list[dict]:
    rows = []
    for row in table:
        if row["row"] == "baseline" and row["arm"] == "":
            rows.append(row)
    return rows



def a_waits(table: list[dict], kind: str, arm: str, seed: str) -> dict | None:
    
    for row in table:
        if row["row"] == kind and row["arm"] == arm and row["seed"] == seed and row["baseline"] != "":
            return row
        
    return None


def mean_of(summary: list[dict], id: str, control: str = "") -> tuple:
    
    for row in summary:
        if row["id"] == id and row["control"] == control:
            return number(row["mean"]), int(row["teams"])
        
    raise ValueError(f"the arm summary has no row {id} {control}")



def team_points(table: list[dict],
                arm: str, 
                column: str, 
                hollow: str | None = None, 
                mark: bool = False,
                count: bool = False, 
                below: bool = False) -> list[dict]:
    
    
    points = []
    for row in team_rows(table, arm):
        
        point = {"seed": int(row["seed"]), "value": number(row[column])}
        
        if hollow is not None:
            point["hollow"] = number(row[hollow])
            
        if mark:
            baseline = a_waits(table, "baseline", arm, row["seed"])
            point["mark"] = None if baseline is None else number(baseline[column])
            
        if count:
            point["numerator"] = row[f"{column}_numerator"]
            point["count"] = row[f"{column}_denominator"]
            
        if below:
            point["below"] = row["below_1_percent"] == "1"
            
        points.append(point)
        
    return points


def lines_of(table: list[dict], column: str, names=None) -> list:
    lines = []
    for row in rule_baselines(table):
        if names is None or row["baseline"] in names:
            lines.append((BASELINES[row["baseline"]][0], number(row[column]), row["baseline"]))
    return lines


def defined_anywhere(table: list[dict], column: str) -> bool:
    for row in table:
        if row["row"] in ("team", "baseline") and number(row[column]) is not None:
            return True
    return False



def has_a_waits(table: list[dict]) -> bool:
    for row in table:
        if row["row"] == "baseline mean":
            return True
    return False


def unit_text(table: list[dict], subject: str = "one team's score") -> str:
    return opening(subject, has_a_waits(table))


def zoom_limits(table: list[dict], arms: list[str], sender: bool, a_waits_shown: bool) -> tuple | None:

    values = []
    for arm in arms:
        for point in team_points(table, arm, "reward", hollow="before_reward" if sender else None, mark=a_waits_shown):
            for value in (point["value"], point.get("hollow"), point.get("mark")):
                if value is not None:
                    values.append(value)

    everything = list(values)
    for _, value, baseline in lines_of(table, "reward"):
        if value is not None:
            everything.append(value)
            if baseline in TEACHERS:
                values.append(value)

    full = max(everything) - min(everything)
    pad = max(0.08 * (max(values) - min(values)), 0.02 * full)
    if max(values) - min(values) + 2 * pad >= 0.5 * full:
        return None

    return min(values) - pad, max(values) + pad


def performance(table: list[dict], summaries: dict, sender: bool, out: Path) -> None:
    
    arms = list(summaries)
    a_waits_shown = has_a_waits(table)
    limits = zoom_limits(table, arms, sender, a_waits_shown)

    panels = len(OUTCOMES) if limits is None else len(OUTCOMES) + 1
    figure, axes = plt.subplots(1, panels, figsize=(10.0 + 3.2 * (panels - len(OUTCOMES)), 5.4))
    outcome_axes = list(axes)
    zoom = None if limits is None else outcome_axes.pop(1)

    parts = ["the teams"]
    if sender:
        parts.append("their initial teams")
    if a_waits_shown:
        parts.append("A always waiting beside them")
    zoom_title = f"the same rewards, zoomed to {', '.join(parts)} and the two teachers"

    rows = []
    
    for axis, id in zip(outcome_axes, OUTCOMES, strict=True):
        points = {}
        means = {}
        for arm in arms:
            
            points[("", arm)] = team_points(table, 
                                            arm, 
                                            id, 
                                            hollow=f"before_{id}" if sender else None,
                                            mark=a_waits_shown)
            
            means[("", arm)] = mean_of(summaries[arm], id)
            
        rows.extend(team_panel(axis, plain_name(id), [""], arms, points, means, is_share(id), lines_of(table, id)))
        axis.set_ylabel(AXIS_LABELS[id])

        if id == "reward" and zoom is not None:
            
            team_panel(zoom, zoom_title, [""], arms, points, means, False, lines_of(table, id))
            zoom.set_ylim(*limits)
            zoom.set_facecolor("#f4f4f4")
            outside = []
            for label, value, _ in lines_of(table, id):
                if value is not None and not limits[0] <= value <= limits[1]:
                    outside.append(f"{label} ({value:.1f})")
            note = "every baseline is inside this view"
            if outside:
                note = "outside this view: " + ", ".join(outside)
            zoom.set_xlabel(wrapped(note, 44), fontsize=6.5)
            rows.append(figure_row(zoom_title, "lower limit", None, "", limits[0], None, None, "zoom"))
            rows.append(figure_row(zoom_title, "upper limit", None, "", limits[1], None, None, "zoom"))

    text = unit_text(table) + " Lines are the rule baselines."
    
    if sender:
        text += " An unfilled dot is the team before training, joined to its trained value."
        
    if a_waits_shown:
        text += " A cross is that seed's score when A always waits next to the fixed B."

    if zoom is not None:
        text += " The grey panel shows the same rewards zoomed to the teams and the two teachers; a baseline outside it is named under it."
        
    text += " " + definitions(list(OUTCOMES))
    finish(figure, axes, QUESTIONS["W1-performance"], text, out, "W1-performance", rows)



def behaviour(table: list[dict], summaries: dict, sender: bool, out: Path) -> None:
    
    arms = list(summaries)
    
    ids = []
    
    for id in SIGNALLING if sender else RECEIVER_BEHAVIOUR:
        if id != "b_unprompted_missed" or defined_anywhere(table, id):
            ids.append(id)
            
    name = "W2-signalling" if sender else "W2-behaviour"
    width = 2.6 * len(ids) + 0.8
    figure, axes = plt.subplots(1, len(ids), figsize=(width, 5.6))
    
    rows = []
    
    for axis, id in zip(axes, ids, strict=True):
        points = {}
        means = {}
        
        for arm in arms:
            points[("", arm)] = team_points(table, arm, id, count=is_share(id), below=sender)
            means[("", arm)] = mean_of(summaries[arm], id)
            
        rows.extend(team_panel(axis, plain_name(id), [""], arms, points, means, is_share(id),
                               lines_of(table, id, RATE_LINES)))

    text = unit_text(table) + " The numbers under an arm are its teams' denominators in seed order. Lines are the rule baselines."
    
    if sender:
        text += " " + ATTACKED_PAIR + " A team that interrupts the attacked pair's server in under 1 percent of intrusion episodes has a red ring."
    else:
        text += " The peer-failure rate counts only choices where B's own server was running and connected; a cue-hidden-unknown B never sees a failure, so it has no such choice."
        
    text += " " + definitions(ids)
        
    finish(figure, axes, QUESTIONS[name], text, out, name, rows)



def responses(table: list[dict], arm: str, controls: list[str]) -> list[tuple]:

    found = []
    for control in controls:
        for row in team_rows(table, arm):
            
            normal = (row["b_responds_to_a_numerator"], row["b_responds_to_a_denominator"], number(row["b_responds_to_a"]))
            
            under = (row[f"b_responds_to_a__{control}_numerator"],
                     row[f"b_responds_to_a__{control}_denominator"],
                     number(row[f"b_responds_to_a__{control}"]))
            
            found.append((control, row["seed"], normal, under, number(row[f"ctrl_b_responds_to_a__{control}"])))

    return found



def response_rows(group: str, found: list[tuple]) -> list[dict]:

    rows = []
    for control, seed, normal, under, _ in found:
        for mark, (numerator, denominator, rate) in (("normal", normal), ("control", under)):
            rows.append(figure_row(plain_name("ctrl_b_responds_to_a"), 
                                   control, 
                                   seed, 
                                   group,
                                   rate,
                                   None,
                                   denominator,
                                   mark,
                                   numerator))

    return rows


def rate_text(numerator: str, denominator: str, rate) -> str:
    counts = f"{float(numerator):g}/{denominator}"
    if rate is None:
        return f"{counts}, undefined"
    return f"{counts} = {rate * 100:.1f}%"


def points_text(difference) -> str:
    if difference is None:
        return "undefined"
    points = difference * 100 + 0.0
    return f"{'+' if points > 0 else ''}{points:.1f} pp"


def response_table(axis, found: list[tuple]) -> None:

    cells = []
    for control, seed, normal, under, difference in found:
        cells.append([control, seed, rate_text(*normal), rate_text(*under), points_text(difference)])

    axis.axis("off")
    axis.set_title("B responded to A's interruption, each cue-visible team's responses over its eligible relevant interruptions in each evaluation", fontsize=7.5)
    
    table = axis.table(cellText=cells,
                       
                       colLabels=["control", 
                                  "training seed",
                                  "normal evaluation",
                                  "under the control",
                                  "normal minus control"],
                       
                       colWidths=[0.34, 0.1, 0.19, 0.19, 0.18],
                       cellLoc="center",
                       bbox=[0.05, 0.0, 0.9, 1.0])
    
    table.auto_set_font_size(False)
    table.set_fontsize(6.5)


def controls(table: list[dict], summaries: dict, sender: bool, out: Path) -> None:
    arms = list(summaries)
    names = []
    for row in summaries[arms[0]]:
        if row["control"] != "" and row["control"] not in names:
            names.append(row["control"])
    ids = ["reward", "b_infected_intervals"]
    if sender:
        ids.extend(["a_interrupt_relevant", "b_responds_to_a"])
    width = 2.8 * len(ids) + 0.8

    found = []
    if sender:
        
        found = responses(table, arms[0], names)
        lines = len(found) + 1
        figure = plt.figure(figsize=(width, 5.6 + 0.19 * lines + 0.5))
        grid = figure.add_gridspec(2, len(ids), height_ratios=[3.6, 0.19 * lines + 0.3])
        axes = []
        for index in range(len(ids)):
            axes.append(figure.add_subplot(grid[0, index]))
        response_table(figure.add_subplot(grid[1, :]), found)
    else:
        figure, axes = plt.subplots(1, len(ids), figsize=(width, 5.6))

    rows = []
    for axis, id in zip(axes, ids, strict=True):
        points = {}
        means = {}
        for control in names:
            
            points[("", control)] = team_points(table, arms[0],
                                                f"ctrl_{id}__{control}",
                                                count=is_share(id) and id != "b_responds_to_a")
            
            means[("", control)] = mean_of(summaries[arms[0]], f"ctrl_{id}", control)
            
        axis.axhline(0.0, color="black", linewidth=0.6, zorder=1)
        rows.extend(team_panel(axis, 
                               plain_name(f"ctrl_{id}"),
                               [""], 
                               names,
                               points,
                               means,
                               False))
        if is_share(id):
            axis.yaxis.set_major_formatter(PercentFormatter(1.0, symbol=" pp"))
        axis.set_xlabel(SIGNS[id], fontsize=6.5)
    rows.extend(response_rows("", found))

    text = (unit_text(table, "one cue-visible team's score")
            + " A control plays the same trained team again with one of B's inputs changed; nothing is retrained. A dot is the team's normal value minus its value under the control.")
    
    if sender:
        text += (" Differences between shares are in percentage points (pp). B's response rate is pooled separately"
                 " in the normal evaluation and in the control, each over its own interruptions; the figure's CSV"
                 " holds the two rates in the rows marked normal and control.")
        
    ctrl_ids = []
    for id in ids:
        ctrl_ids.append(f"ctrl_{id}")
    text += " " + definitions(ctrl_ids)
        
    finish(figure, axes, QUESTIONS["W3-controls"], text, out, "W3-controls", rows)


def curve(axis, panel: str, xs: list, series: list, everyone: int, percent: bool, rows: list) -> None:
    
    for index, (arm, means, sds, teams) in enumerate(series):
        
        colour = SERIES_COLOURS[index % len(SERIES_COLOURS)]
        
        ys = []
        lower = []
        upper = []
        
        for x, mean, sd, count in zip(xs, means, sds, teams, strict=True):
            
            rows.append(figure_row(panel, arm, None, x, mean, sd, count, "undefined" if mean is None else "mean"))
            ys.append(float("nan") if mean is None else mean)
            spread = 0.0 if sd is None else sd
            lower.append(float("nan") if mean is None else mean - spread)
            upper.append(float("nan") if mean is None else mean + spread)
            
            if mean is not None and count < everyone:
                axis.plot([x], 
                          [mean], 
                          "o",
                          markerfacecolor="white", 
                          markeredgecolor=colour, 
                          markersize=3.5, 
                          zorder=4,
                          label="a mean over fewer teams than the arm has")
                
                
        axis.plot(xs, ys, "-o", color=colour, linewidth=1.0, markersize=2, label=arm)
        axis.fill_between(xs, lower, upper, color=colour, alpha=0.18, linewidth=0)
        
    axis.set_title(wrapped(panel, 48))
    axis.set_xlabel("training iteration")
    axis.xaxis.set_major_locator(MaxNLocator(integer=True))
    
    if percent:
        axis.yaxis.set_major_formatter(PercentFormatter(1.0))


def learning(table: list[dict], summaries: dict, curves: dict, behaviours: dict, sender: bool, out: Path) -> None:
    
    
    arms = list(summaries)
    count = 3 if sender else 1
    width = 3.6 * count + 0.8
   
    figure, axes = plt.subplots(1, count, figsize=(width, 5.2), squeeze=False, sharex=True)
    axes = list(axes[0])
    rows = []

    xs = []
    series = []
    for row in curves[arms[0]]:
        xs.append(int(row["iteration"]))
    for arm in arms:
        means = []
        sds = []
        teams = []
        for row in curves[arm]:
            means.append(number(row["mean"]))
            sds.append(number(row["sd"]))
            teams.append(int(row["teams"]))
        series.append((arm, means, sds, teams))
    everyone = len(team_rows(table, arms[0]))
    curve(axes[0], "team reward per training episode", xs, series, everyone, False, rows)
    for label, value, baseline in lines_of(table, "reward", TEACHERS):
        _, colour, style = BASELINES[baseline]
        axes[0].axhline(value, color=colour, linestyle=style, linewidth=0.9, label=f"{label}, evaluated greedily")
        rows.append(figure_row("team reward per training episode", label, None, "", value, None, None, "baseline"))
        
        
    for index, arm in enumerate(arms):
        baseline = a_waits(table, "baseline mean", arm, "")
        if baseline is not None:
            value = number(baseline["reward"])
            axes[0].axhline(value, color=SERIES_COLOURS[index], linestyle=BASELINES["a-waits-with-fixed-b"][2],
                            linewidth=0.9, label="A always waits next to the fixed B, mean of the seeds, in the arm's colour")
            rows.append(figure_row("team reward per training episode", arm, None, "", value, None, None, "a-waits"))

    if sender:
        for axis, id in zip(axes[1:], ("a_interrupts", "b_responds_to_a"), strict=True):
            block_xs = []
            for row in behaviours[arms[0]]:
                block_xs.append(int(row["last_iteration"]))
            block_series = []
            for arm in arms:
                means = []
                sds = []
                teams = []
                for row in behaviours[arm]:
                    means.append(number(row[f"{id}_mean"]))
                    sds.append(number(row[f"{id}_sd"]))
                    teams.append(int(row[f"{id}_teams"]))
                block_series.append((arm, means, sds, teams))
            curve(axis, plain_name(id) + ", per block of training iterations", block_xs, block_series, everyone,
                  is_share(id), rows)

    text = ("The line is the mean over the arm's teams and the band one standard deviation around it. An unfilled point is a mean over fewer than the arm's teams. Training episodes sample their actions, while the teachers' lines are their rewards in the greedy evaluation episodes.")
    
    if sender:
        text += (" The two lower panels are computed per block of 100 training iterations and drawn at the block's last iteration; a gap is a block with no value. "
                 + definitions(["a_interrupts", "b_responds_to_a"]))
        
        
    finish(figure, axes, QUESTIONS["W4-learning"], text, out, "W4-learning", rows)


def probe(table: list[dict], summaries: dict, out: Path) -> None:
    arms = list(summaries)
    width = 2.7 * len(SITUATIONS) + 0.8
    figure, axes = plt.subplots(1, len(SITUATIONS), figsize=(width, 5.6))
    rows = []
    denominators = []
    for axis, situation in zip(axes, SITUATIONS, strict=True):
        id = f"probe_interrupt_{situation}"
        points = {}
        means = {}
        for arm in arms:
            points[("", arm)] = team_points(table, arm, id, hollow=f"probe_greedy_interrupt_{situation}")
            means[("", arm)] = mean_of(summaries[arm], id)
        rows.extend(team_panel(axis, plain_name(id), [""], arms, points, means, True, join_hollow=False,
                               link_series=True))
        counts = []
        for row in team_rows(table, arms[0]):
            counts.append(f"seed {row['seed']} {row[f'{id}_denominator']}")
        denominators.append(f"{situation.replace('_', ' ')}: " + ", ".join(counts))

    text = (unit_text(table, "one team's A")
            + " A filled dot is A's mean probability of Restore or Isolate, an unfilled dot is the share of A's greedy choices that Restore or Isolate a server. The two A's of the same seed are joined by a thin line. Observations behind each seed, the same for both arms: "
            + "; ".join(denominators) + ".")
    
    probe_ids = []
    for situation in SITUATIONS:
        probe_ids.append(f"probe_interrupt_{situation}")
    text += " " + definitions(probe_ids)
        
    finish(figure, axes, QUESTIONS["W5-probe"], text, out, "W5-probe", rows)


def draw_world(table: list[dict], summaries: dict, curves: dict, behaviours: dict, sender: bool, out: Path) -> None:
    performance(table, summaries, sender, out)
    behaviour(table, summaries, sender, out)
    controls(table, summaries, sender, out)
    learning(table, summaries, curves, behaviours, sender, out)
    if sender:
        probe(table, summaries, out)
