import re
import textwrap
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter

from measurements.glossary import DIFFERENCE, EPISODE_TOTAL, measurement_rows
from measurements.tables import optional_number, write_csv

matplotlib.use("Agg")


plt.rcParams.update({"svg.hashsalt": "experiment-runs", 
                     "svg.fonttype": "none", 
                     "font.size": 8,
                     "axes.spines.top": False,
                     "axes.spines.right": False,
                     "axes.titlesize": 8.5,
                     "legend.fontsize": 7,
                     "legend.frameon": False})


SERIES_COLOURS = ("#2b6cb0", "#dd6b20")
TEAM_DOT = 4.5


BASELINES = {"always-wait": ("always wait", "#444444", (0, (4, 2))),
             "inspect-teacher": ("inspect-first teacher", "#2f855a", (0, (1, 1.5))),
             "restore-teacher": ("restore-on-warning teacher", "#9b2c2c", (0, (6, 2, 1, 2))),
             "random": ("uniform random", "#888888", (0, (2, 3))),
             "a-waits-with-fixed-b": ("A always waits next to the fixed B", "#555555", (0, (3, 1)))}

FIGURE_COLUMNS = ["panel", "series", "seed", "x", "value", "sd", "numerator", "count", "mark"]

GLOSSARY = {}
for _row in measurement_rows(True):
    GLOSSARY[_row["id"]] = _row


def plain_name(id: str) -> str:
    return GLOSSARY[id]["plain_name"]


def base_kind(id: str) -> str:
    row = GLOSSARY[id]
    if row["kind"] == DIFFERENCE:
        return GLOSSARY[row["base_id"]]["kind"]
    return row["kind"]


def is_share(id: str) -> bool:
    return base_kind(id) != EPISODE_TOTAL


def describe(id: str) -> str:
    row = GLOSSARY[id]
    name = row["plain_name"]
    return f"{name[0].upper()}{name[1:]}: over {row['population']} - denominator: {row['denominator']}"


def definitions(ids: list[str]) -> str:
    entries = []
    for id in ids:
        entries.append(describe(id))
    return " | ".join(entries)


def opening(subject: str, fixed: bool) -> str:
    tail = ", with B fixed." if fixed else "."
    return (f"One dot represents {subject}, where one team is one pair of defenders A and B trained corresponding "
            f"to one seed{tail} The black line is the mean of the teams that have a value; a team without one is "
            "not drawn.")


def wrapped(text: str, width: int) -> str:
    return "\n".join(textwrap.wrap(text, width))


def world_label(world: str) -> str:
    return wrapped(world.replace("-", " "), 14)


def panel_title(axis, text: str) -> None:
    inches = axis.get_position().width * axis.figure.get_figwidth()
    axis.set_title(wrapped(text, max(38, int(inches * 13))))


def under_axis(axis, x: float, text: str, size: float) -> None:
    axis.annotate(text, (x, 0), xycoords=axis.get_xaxis_transform(), xytext=(0, -5), textcoords="offset points",
                  ha="center", va="top", fontsize=size, color="#666666", annotation_clip=False)
    axis.tick_params(axis="x", pad=13)


def number(cell) -> float | None:
    if cell is None:
        return None
    return optional_number(cell)


def figure_row(panel: str, series: str, seed, x, value, sd, count, mark: str, numerator=None) -> dict:
    return {"panel": panel, 
            "series": series,
            "seed": seed, 
            "x": x, 
            "value": value, 
            "sd": sd,
            "numerator": numerator,
            "count": count,
            "mark": mark}


def team_panel(axis,
               panel: str, 
               groups: list[str],
               series: list[str], 
               points: dict, 
               means: dict, 
               percent: bool,
               lines: list = (),
               marks: list = (), 
               join_hollow: bool = True,
               link_series: bool = False) -> list[dict]:
    

    rows = []
    width = 0.8 / len(series)
    positions = {}
    counted = False
    counts_by_series = {}
    teams_by_series = {}

    for g, group in enumerate(groups):
        
        for s, name in enumerate(series):
            
            colour = SERIES_COLOURS[s % len(SERIES_COLOURS)]
            centre = g + (s - (len(series) - 1) / 2) * width
            group_points = points.get((group, name), [])
            undefined = 0
            counts = []

            for index, point in enumerate(group_points):
                offset = 0.0
                if len(group_points) > 1:
                    offset = (index / (len(group_points) - 1) - 0.5) * width * 0.6
                x = centre + offset
                value = point["value"]
                hollow = point.get("hollow")

                if hollow is not None:
                    
                    axis.plot([x - 0.035], 
                              [hollow],
                              "o", 
                              markerfacecolor="white",
                              markeredgecolor=colour,
                              markersize=TEAM_DOT, 
                              zorder=3, 
                              label="initial team, before training" if join_hollow
                              else "share of greedy choices")
                    
                    rows.append(figure_row(panel, 
                                           name,
                                           point["seed"], 
                                           group,
                                           hollow, 
                                           None, 
                                           None, 
                                           "before" if join_hollow else "greedy"))
                    
                    
                if value is None:
                    undefined += 1
                    rows.append(figure_row(panel, 
                                           name, 
                                           point["seed"], 
                                           group, 
                                           None, 
                                           None, 
                                           point.get("count"),
                                           "undefined", 
                                           point.get("numerator")))
                    
                    
                    continue

                axis.plot([x], [value], "o", color=colour, markersize=TEAM_DOT, zorder=3, label=name)
                rows.append(figure_row(panel, 
                                       name, 
                                       point["seed"],
                                       group,
                                       value,
                                       None, 
                                       point.get("count"), 
                                       "team",
                                       point.get("numerator")))
                positions[(g, point["seed"], s)] = (x, value)
                
                
                if hollow is not None and join_hollow:
                    axis.plot([x - 0.035, x], [hollow, value], "-", color=colour, linewidth=0.6, zorder=2)
                    
                    
                if point.get("mark") is not None:
                    
                    axis.plot([x + 0.035], 
                              [point["mark"]],
                              "x", 
                              color="#555555",
                              markersize=3.5, 
                              zorder=3,
                              label="A always waits next to the fixed B, same seed")
                    
                    rows.append(figure_row(panel, name, point["seed"], group, point["mark"], None, None, "a-waits"))
                
                
                if point.get("count") is not None:
                    counted = True
                    counts.append(str(point["count"]))
                    
                    
                if point.get("below"):
                    axis.plot([x], [value], "o", markerfacecolor="none", markeredgecolor="#9b2c2c",
                              markersize=TEAM_DOT + 3, markeredgewidth=0.8, zorder=3,
                              label="team under 1 percent interruptions of the attacked pair's server")


            mean, teams = means.get((group, name), (None, 0))
            counts_by_series[name] = counts
            teams_by_series[name] = teams
            
            if mean is not None:
                
                axis.plot([centre - width * 0.4, centre + width * 0.4], [mean, mean], "-", color="black",
                          linewidth=1.4, zorder=4, label="mean of the teams that have a value")
                
                rows.append(figure_row(panel, name, None, group, mean, None, teams, "mean"))
                
                
            if group_points and undefined == len(group_points):
                under_axis(axis, centre, "undefined", 6)
            elif undefined:
                under_axis(axis, centre, f"{undefined} undefined", 5.5)


        if link_series:
            
            seeds = []
            
            for link_group, seed, _ in positions:
                if link_group == g and seed not in seeds:
                    seeds.append(seed)
                    
                    
            for seed in seeds:
                xs = []
                ys = []
                
                for s in range(len(series)):
                    if (g, seed, s) in positions:
                        xs.append(positions[(g, seed, s)][0])
                        ys.append(positions[(g, seed, s)][1])
                        
                if len(xs) > 1:
                    axis.plot(xs, ys, "-", color="#999999", linewidth=0.5, zorder=1)


    for label, value, baseline in lines:
        
        if value is None:
            continue
        
        _, colour, style = BASELINES[baseline]
        
        axis.axhline(value, color=colour, linestyle=style, linewidth=0.9, zorder=1, label=label)
        
        rows.append(figure_row(panel, label, None, "", value, None, None, "baseline"))



    for label, group, name, value, baseline, colour in marks:
        
        if value is None:
            continue
        
        _, line_colour, style = BASELINES[baseline]
        centre = groups.index(group)
        half = 0.45
        
        if name is not None:
            centre += (series.index(name) - (len(series) - 1) / 2) * width
            half = width / 2
            
        axis.plot([centre - half, centre + half], [value, value], color=colour or line_colour, linestyle=style,
                  linewidth=0.9, zorder=1, label=label)
        
        mark = "a-waits" if baseline == "a-waits-with-fixed-b" else "baseline"
        rows.append(figure_row(panel, label if name is None else name, None, group, value, None, None, mark))


    panel_title(axis, panel)

    axis.margins(y=0.05)
    axis.set_xlim(-0.6, len(groups) - 0.4)
    
    if groups == [""]:
        

        centres = []
        labels = []
        
        for s, name in enumerate(series):
            centres.append((s - (len(series) - 1) / 2) * width)
            label = wrapped(name, 12) + f"\n{teams_by_series.get(name, 0)} teams"
            if counted and counts_by_series.get(name):
                label += "\n" + wrapped("n = " + ", ".join(counts_by_series[name]), 20)
            labels.append(label)
            
        axis.set_xticks(centres)
        axis.set_xticklabels(labels, fontsize=6.5)
        
    else:
        axis.set_xticks(range(len(groups)))
        axis.set_xticklabels([world_label(group) for group in groups])
        
    if percent:
        low, high = axis.get_ylim()
        axis.set_ylim(min(low, -0.02), max(high, 0.22))
        axis.yaxis.set_major_formatter(PercentFormatter(1.0))

    return rows


def finish(figure, axes, question: str, text: str, folder: Path, name: str, rows: list[dict] | None) -> None:

    width, height = figure.get_size_inches()
    renderer = figure.canvas.get_renderer()

    seen = {}
    for axis in axes:
        handles, labels = axis.get_legend_handles_labels()
        for handle, label in zip(handles, labels, strict=True):
            if label not in seen:
                seen[label] = handle

    title = figure.text(0.5, 1 - 0.12 / height, wrapped(question, int(width * 10)), fontsize=10.5,
                        fontweight="bold", ha="center", va="top")
    top = 1 - (0.2 + title.get_window_extent(renderer).height / figure.dpi) / height

    columns = len(seen)
    legend = figure.legend(list(seen.values()), list(seen), loc="upper center", bbox_to_anchor=(0.5, top),
                           ncol=columns)
    while columns > 1 and legend.get_window_extent(renderer).width > 0.97 * width * figure.dpi:
        legend.remove()
        columns -= 1
        legend = figure.legend(list(seen.values()), list(seen), loc="upper center", bbox_to_anchor=(0.5, top),
                               ncol=columns)
    top -= (0.1 + legend.get_window_extent(renderer).height / figure.dpi) / height

    figure.supxlabel(text, x=0.012, ha="left", fontsize=6.5, color="#333333", wrap=True)
    figure.set_layout_engine("constrained", rect=(0, 0, 1, top), w_pad=0.08, h_pad=0.08, wspace=0.08,
                             hspace=0.12)
    save(figure, folder, name, rows)


def save(figure, folder: Path, name: str, rows: list[dict] | None) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    figure.savefig(folder / f"{name}.png", dpi=150)
    svg = folder / f"{name}.svg"
    figure.savefig(svg, metadata={"Date": None})

    text = svg.read_text(encoding="utf-8")
    for index, identifier in enumerate(re.findall(r'<clipPath id="([^"]+)"', text)):
        replacement = f"clip{index}"
        text = text.replace(f'id="{identifier}"', f'id="{replacement}"')
        text = text.replace(f"url(#{identifier})", f"url(#{replacement})")
    svg.write_text(text, encoding="utf-8")
    if rows is not None:
        write_csv(folder / f"{name}.csv", rows, FIGURE_COLUMNS)
    plt.close(figure)
