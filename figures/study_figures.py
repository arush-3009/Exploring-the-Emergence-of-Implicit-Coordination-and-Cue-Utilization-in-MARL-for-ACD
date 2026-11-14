from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import MaxNLocator, PercentFormatter

from figures.style import (
    BASELINES,
    SERIES_COLOURS,
    definitions,
    finish,
    is_share,
    number,
    opening,
    plain_name,
    team_panel,
    under_axis,
    world_label,
    wrapped,
)
from figures.world_figures import (
    ATTACKED_PAIR,
    AXIS_LABELS,
    OUTCOMES,
    RECEIVER_BEHAVIOUR,
    SIGNALLING,
    SIGNS,
    SITUATIONS,
    TEACHERS,
    defined_anywhere,
    has_a_waits,
    mean_of,
    response_rows,
    responses,
    rule_baselines,
    team_points,
)
from studies.paths import study_title

QUESTIONS = {"S1-performance": "How well do the teams defend?",
             
             "S2-behaviour": "Does B act on its partner's request failures?",
             
             "S2-signalling": "Does A interrupt its servers in ways B can see, and does B respond?",
             
             "S3-controls": "What do the cue-visible teams lose when the cue is removed at evaluation?",
             
             "S4-probe": "Given the same inputs, how likely is A to interrupt?",
             
             "sender-studies-summary": "In how many teams does A interrupt the attacked pair's server in at least 1 percent of intrusion episodes?"}


PANEL_HEIGHT = 2.6


def unit_text(worlds: dict, subject: str = "one team's score") -> str:
    table, _ = next(iter(worlds.values()))
    return opening(subject, has_a_waits(table))


def panel(axis, 
          worlds: dict,
          id: str, 
          series: list[str],
          column: str | None = None,
          hollow: str | None = None,
          count: bool = False, 
          below: bool = False, 
          control: bool = False, 
          marks: list = ()) -> list[dict]:

    points = {}
    means = {}
    for world, (table, summaries) in worlds.items():
        arms = list(summaries)
        for name in series:
            if control:
                points[(world, name)] = team_points(table, arms[0], f"{column}__{name}")
                means[(world, name)] = mean_of(summaries[arms[0]], column, name)
            else:
                points[(world, name)] = team_points(table, name, id, hollow=hollow, count=count, below=below)
                means[(world, name)] = mean_of(summaries[name], id)
    title = plain_name(column if control else id)
    rows = team_panel(axis, title, list(worlds), series, points, means, is_share(id) and not control, marks=marks,
                      join_hollow=False)
    
    if control and is_share(id):
        axis.yaxis.set_major_formatter(PercentFormatter(1.0, symbol=" pp"))
    return rows


def performance(worlds: dict, out: Path) -> None:
    arms = list(next(iter(worlds.values()))[1])
    figure, axes = plt.subplots(len(OUTCOMES), 1, figsize=(8.5, PANEL_HEIGHT * len(OUTCOMES) + 2.8))
    rows = []
    for axis, id in zip(axes, OUTCOMES, strict=True):
        marks = []
        for world, (table, _) in worlds.items():
            for row in rule_baselines(table):
                if row["baseline"] in TEACHERS:
                    marks.append((BASELINES[row["baseline"]][0], world, None, number(row[id]), row["baseline"], None))
            for index, arm in enumerate(arms):
                for row in table:
                    if row["row"] == "baseline mean" and row["arm"] == arm:
                        marks.append(("A always waits next to the fixed B, mean of the seeds, over the arm's dots",
                                      world, arm, number(row[id]), row["baseline"], SERIES_COLOURS[index]))
        rows.extend(panel(axis, worlds, id, arms, marks=marks))
        axis.set_ylabel(wrapped(AXIS_LABELS[id], 26))

    text = unit_text(worlds) + " " + definitions(list(OUTCOMES))
    
    finish(figure, list(axes), QUESTIONS["S1-performance"], text, out, "S1-performance", rows)


def behaviour(worlds: dict, sender: bool, out: Path) -> None:
    arms = list(next(iter(worlds.values()))[1])
    ids = []
    for id in SIGNALLING if sender else RECEIVER_BEHAVIOUR:
        defined = False
        for table, _ in worlds.values():
            if defined_anywhere(table, id):
                defined = True
        if id != "b_unprompted_missed" or defined:
            ids.append(id)
    name = "S2-signalling" if sender else "S2-behaviour"
    figure, axes = plt.subplots(len(ids), 1, figsize=(8.5, PANEL_HEIGHT * len(ids) + 3.2))
    rows = []
    for axis, id in zip(axes, ids, strict=True):
        series = arms[:1] if id == "b_acts_on_peer_failure" else arms
        rows.extend(panel(axis, worlds, id, series, count=is_share(id), below=sender))


    text = unit_text(worlds) + " Every team's denominators are in the figure's CSV and in each world's figure W2."
    if sender:
        text += " " + ATTACKED_PAIR + " A team that interrupts the attacked pair's server in under 1 percent of intrusion episodes has a red ring."
    else:
        text += " The peer-failure rate is shown for the cue-visible arm only and counts only choices where B's own server was running and connected."
        
    text += " " + definitions(ids)
        
    finish(figure, list(axes), QUESTIONS[name], text, out, name, rows)


def controls(worlds: dict, sender: bool, out: Path) -> None:
    first_summaries = next(iter(worlds.values()))[1]
    arms = list(first_summaries)
    names = []
    
    for row in first_summaries[arms[0]]:
        
        if row["control"] != "" and row["control"] not in names:
            names.append(row["control"])
            
    ids = ["reward", "b_infected_intervals"]
    if sender:
        ids.append("b_responds_to_a")
        
    figure, axes = plt.subplots(len(ids), 1, figsize=(8.5, PANEL_HEIGHT * len(ids) + 3.0))
    rows = []
    
    for axis, id in zip(axes, ids, strict=True):
        axis.axhline(0.0, color="black", linewidth=0.6, zorder=1)
        rows.extend(panel(axis, worlds, id, names, column=f"ctrl_{id}", control=True))
        axis.set_ylabel(wrapped(SIGNS[id], 26), fontsize=6.5)

    if sender:
        for world, (table, summaries) in worlds.items():
            rows.extend(response_rows(world, responses(table, next(iter(summaries)), names)))

    text = (unit_text(worlds, "one cue-visible team's score") + " A control plays the same trained team again with one of B's inputs changed; nothing is retrained. A dot is the team's normal value minus its value under the control.")

    if sender:
        text += (" Differences between shares are in percentage points (pp). B's response rate is pooled separately"
                 " in the normal evaluation and in the control, each over its own interruptions; the figure's CSV"
                 " holds the two rates in the rows marked normal and control.")
    
    ctrl_ids = []
    for id in ids:
        ctrl_ids.append(f"ctrl_{id}")
    text += " " + definitions(ctrl_ids)
        
    finish(figure, list(axes), QUESTIONS["S3-controls"], text, out, "S3-controls", rows)


def probe(worlds: dict, out: Path) -> None:
    arms = list(next(iter(worlds.values()))[1])
    figure, axes = plt.subplots(len(SITUATIONS), 1, figsize=(8.5, PANEL_HEIGHT * len(SITUATIONS) + 2.8))
    rows = []
    for axis, situation in zip(axes, SITUATIONS, strict=True):
        rows.extend(panel(axis, worlds, f"probe_interrupt_{situation}", arms,
                          hollow=f"probe_greedy_interrupt_{situation}"))

    text = (unit_text(worlds, "one team's A") + " A filled dot is A's mean probability of Restore or Isolate, an unfilled dot is the share of A's greedy choices that Restore or Isolate a server. Each world's figure W5 gives the observations behind each seed.")
    
    probe_ids = []
    for situation in SITUATIONS:
        probe_ids.append(f"probe_interrupt_{situation}")
    text += " " + definitions(probe_ids)
        
    finish(figure, list(axes), QUESTIONS["S4-probe"], text, out, "S4-probe", rows)


def draw_study(worlds: dict, sender: bool, out: Path) -> None:
    performance(worlds, out)
    behaviour(worlds, sender, out)
    controls(worlds, sender, out)
    if sender:
        probe(worlds, out)


def draw_cross_study(summary: list[dict], out: Path) -> None:
    
    studies = []
    worlds = []
    arms = []
    
    for row in summary:
        for name, found in ((row["study"], studies), (row["world"], worlds), (row["arm"], arms)):
            if name not in found:
                found.append(name)

    most = 1
    for row in summary:
        most = max(most, int(row["a_interrupt_relevant_teams"]))

    figure, axes = plt.subplots(len(studies), 1, figsize=(8.5, PANEL_HEIGHT * len(studies) + 2.4))
    axes = list(axes) if len(studies) > 1 else [axes]
    width = 0.8 / len(arms)
    for axis, study in zip(axes, studies, strict=True):
        for row in summary:
            if row["study"] != study:
                continue
            g = worlds.index(row["world"])
            s = arms.index(row["arm"])
            x = g + (s - (len(arms) - 1) / 2) * width
            teams = number(row["teams_at_or_above_1_percent"])
            if teams is None:
                under_axis(axis, x, "undefined", 6)
                continue
            axis.bar([x], [teams], width=width * 0.9, color=SERIES_COLOURS[s], label=row["arm"])
            axis.annotate(f"{teams:g} of {row['a_interrupt_relevant_teams']}", (x, teams), xytext=(0, 2),
                          textcoords="offset points", ha="center", fontsize=5.5)
        axis.set_title(study_title(study))
        axis.set_xticks(range(len(worlds)))
        axis.set_xticklabels([world_label(world) for world in worlds])
        axis.set_xlim(-0.6, len(worlds) - 0.4)
        axis.set_ylabel("teams at or above 1%")
        axis.set_ylim(0, most * 1.15)
        axis.yaxis.set_major_locator(MaxNLocator(integer=True))

    text = ("A bar is the number of teams of the arm that interrupt the attacked pair's server in at least 1 percent of intrusion episodes, out of the teams written above it. "
            + ATTACKED_PAIR
            + " Studies 3 to 5 differ only in where A starts; in study 2 B starts from the teacher and learns as well. "
            + definitions(["a_interrupt_relevant"]))
    
    
    finish(figure, axes, QUESTIONS["sender-studies-summary"], text, out, "sender-studies-summary", None)

