# One eval episode shown as an HTML page.

# From the repository root, for an evaluation folder

#     uv run --locked python -m tools.timeline runs/<study>/worlds/<world>/training-arms/cue-visible/teams/seed0-team \\
#         --seed 2001 --episode 17 [--episodes <that folder's episodes.csv>] [--out page.html]


import argparse
import csv
import html
from pathlib import Path

from episodes.record import EpisodeRecord
from episodes.record_io import read_records, read_run_json
from measurements.facts import FINDINGS, PEER_RESULTS
from measurements.glossary import (
    COUNT_KINDS,
    EPISODE_INDICATOR,
    EPISODE_KINDS,
    base_rows,
)

STATE_COLOURS = {"clean": "#d7efcf", "compromised": "#f5a9a2"}

ACTION_COLOURS = {"restore": "#3b6fc9", "reconnect": "#2aa596", "inspect": "#d9b32f", "isolate": "#ec7f2c"}

SHORT_LABELS = {"restore": "rst", "reconnect": "rc", "inspect": "insp", "isolate": "iso"}

KIND_NAMES = {"team-evaluation": "team",
              "before-evaluation": "initial team", 
              "baseline": "baseline",
              "control": "control"}

STYLE = """
* { box-sizing: border-box; }
body { font-family: -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif; font-size: 13px; color: #1d1d1f;
  margin: 0; padding: 14px 18px 10px 18px; background: #ffffff; }
header.top { display: flex; align-items: flex-start; justify-content: space-between; gap: 24px; }
header.top > div:first-child { flex: 1 1 auto; min-width: 0; }
.stats { flex: 0 0 auto; }
h1 { font-size: 22px; margin: 0; line-height: 1.2; }
.fields { margin-top: 6px; font-size: 12.5px; }
.field { display: flex; gap: 8px; line-height: 1.5; }
.field .name { width: 92px; min-width: 92px; font-weight: 700; color: #1e40af; text-align: right; }
.field .value { color: #1d1d1f; word-break: break-all; }
.stats { display: flex; gap: 10px; flex-wrap: wrap; }
.stat { border: 1px solid #e3e3e3; border-radius: 6px; padding: 6px 12px; min-width: 110px; background: #fafafa; }
.stat .k { font-size: 11px; color: #666; text-transform: uppercase; letter-spacing: 0.04em; }
.stat .v { font-size: 20px; font-weight: 700; margin-top: 1px; }
.stat.intrusion .v { color: #c2410c; }
.stat.good .v { color: #15803d; }
.stat.bad .v { color: #b91c1c; }
.story { margin: 10px 0 0 0; padding: 8px 12px; border-left: 4px solid #3b6fc9; background: #f3f6fc; font-size: 13px; }
.story p { margin: 2px 0; }
.reason { margin: 10px 0 0 0; padding: 8px 12px; border-left: 4px solid #f2b705; background: #fffbea; font-size: 13px; }
.measured { margin: 8px 0 2px 0; font-size: 12px; color: #333; column-count: 2; column-gap: 28px; }
.measured div { line-height: 1.45; padding: 1px 0; break-inside: avoid; }
.legend { display: flex; gap: 28px; flex-wrap: wrap; align-items: flex-start; margin: 12px 0 8px 0; font-size: 12px;
  color: #333; }
table.key { border-collapse: collapse; border: 1px solid #ccc; }
table.key th { text-align: left; font-weight: 600; color: #555; background: #f0f0f0; padding: 3px 10px; border: 1px solid #ccc; }
table.key td { padding: 2px 10px; white-space: nowrap; border: 1px solid #ddd; }
.swatch { display: inline-block; width: 16px; height: 16px; vertical-align: -3px; margin-right: 5px; border: 1px solid #bbb; border-radius: 2px; }
.swatch.isolated { background-image: repeating-linear-gradient(45deg, transparent 0 3px, rgba(0,0,0,0.3) 3px 5px); background-color: #d7efcf; }
.swatch.outage { background-image: repeating-linear-gradient(-45deg, transparent 0 3px, rgba(146,64,14,0.5) 3px 5px); background-color: #d7efcf; }
.swatch.stopped { background-color: #d7efcf; box-shadow: inset 0 -5px 0 #444; }
.swatch.patched { background-color: #d7efcf; box-shadow: inset 0 0 0 2px #3b6fc9; }
.swatch.first { background: #3b6fc9; box-shadow: 0 0 0 2px #f2b705; }
.grid-wrap { overflow-x: auto; padding-bottom: 6px; }
h2 { font-size: 16px; margin: 14px 0 2px 0; }
table.grid { border-collapse: separate; border-spacing: 2px; table-layout: fixed; }
table.grid th, table.grid td { width: 30px; min-width: 30px; height: 28px; padding: 0; text-align: center; font-size: 12px;
  white-space: nowrap; overflow: hidden; border-radius: 2px; }
table.grid th.label, table.grid td.label { width: 170px; min-width: 170px; text-align: right; padding-right: 8px; font-weight: 600;
  background: #fff; position: sticky; left: 0; z-index: 1; }
table.grid th.interval { background: #eceff3; font-weight: 600; color: #333; height: 24px; }
table.grid th.intrusion { background: #f59e0b; color: #fff; font-weight: 800; }
table.grid tr.zone td { height: 22px; }
table.grid tr.zone td.label { text-align: left; background: #e5e7eb; color: #111; font-size: 12px; text-transform: uppercase; letter-spacing: 0.04em; }
table.grid tr.zone td.fill { background: #e5e7eb; }
td.server { font-size: 15px; }
td.col-intrusion { box-shadow: inset 2px 0 0 #f59e0b; }
td.isolated { background-image: repeating-linear-gradient(45deg, transparent 0 3px, rgba(0,0,0,0.3) 3px 5px); }
td.outage { background-image: repeating-linear-gradient(-45deg, transparent 0 3px, rgba(146,64,14,0.5) 3px 5px); }
td.isolated.outage { background-image: repeating-linear-gradient(45deg, transparent 0 3px, rgba(0,0,0,0.3) 3px 5px),
  repeating-linear-gradient(-45deg, transparent 0 3px, rgba(146,64,14,0.5) 3px 5px); }
td.stopped { box-shadow: inset 0 -5px 0 #444; }
td.patched { box-shadow: inset 0 0 0 2px #3b6fc9; }
td.stopped.patched { box-shadow: inset 0 0 0 2px #3b6fc9, inset 0 -5px 0 #444; }
td.col-intrusion.patched { box-shadow: inset 0 0 0 2px #3b6fc9, inset 2px 0 0 #f59e0b; }
td.action { color: #fff; font-weight: 700; text-align: left; padding-left: 5px; font-size: 12px; }
td.action.first { box-shadow: 0 0 0 2px #f2b705; }
td.noop { color: #777; font-size: 13px; }
td.wait { color: #c0c0c0; font-size: 14px; }
td.defender-label { color: #1d1d1f; }
td.reward { font-weight: 700; color: #222; }
td.running { font-size: 11px; color: #555; background: #f7f7f7; }
"""


def timeline_html(record: EpisodeRecord,
                  run: dict,
                  metrics: dict | None = None,
                  reason: str | None = None,
                  reference: float | None = None) -> str:

    body = _header(record, run, metrics, reference, heading=True)
    
    if reason:
        body += f'<div class="reason">{html.escape(reason)}</div>'
        
    body += _legend() + _grid(record, run, metrics)
    return _page(_heading(record, run), body)


def stacked_html(entries: list[tuple], reason: str) -> str:

    first = entries[0][0]
    parts = [(f"<h1>Episode {first.episode} of evaluation seed {first.evaluation_seed}, {len(entries)} evaluations</h1>"), f'<div class="reason">{html.escape(reason)}</div>', _legend()]
    for record, run, metrics, reference in entries:
        parts.append(f"<h2>{html.escape(_heading(record, run))}</h2>")
        parts.append(_header(record, run, metrics, reference, heading=False) + _grid(record, run, metrics))
    return _page(f"episode {first.evaluation_seed}-{first.episode}, {len(entries)} evaluations", "".join(parts))


def _page(title: str, body: str) -> str:
    return (f"<!DOCTYPE html><html><head><meta charset='utf-8'><title>{html.escape(title)}</title> <style>{STYLE}</style></head><body>{body}</body></html>")


def _where(run: dict) -> str:
    kind = run["kind"]
    if kind == "baseline" and "arm" not in run:
        return f"baseline {run['rule']}"
    if kind == "baseline":
        return f"baseline {run['rule']}, {run['arm']}, seed {run['seed']}"
    if kind == "control":
        return f"{run['arm']}, seed {run['seed']}, under the control {run['control']}"
    text = f"{run['arm']}, seed {run['seed']}"
    if kind == "before-evaluation":
        text += ", initial team"
    return text


def _heading(record: EpisodeRecord, run: dict) -> str:
    return (f"{run['world']} › {_where(run)} (evaluation seed {record.evaluation_seed}, episode {record.episode})")


def _policy_text(entry: dict) -> str:
    if entry["type"] == "rule":
        return f"rule {entry['rule']}"
    return f"greedy actor from {entry['weights']}"


def _header(record: EpisodeRecord, run: dict, metrics: dict | None, reference: float | None, heading: bool) -> str:

    intrusion = record.script["intrusion"]
    total = record.total_reward
    tiles = [("intrusion", f"{intrusion['server']} at {intrusion['interval']}" if intrusion else "none",
              "intrusion" if intrusion else ""), ("total reward", f"{total:g}", "")]
    if reference is not None:
        gain = total - reference
        tiles.append(("always-wait", f"{reference:g}", ""))
        tiles.append(("gain", f"{gain:+g}", "good" if gain > 0 else "bad" if gain < 0 else ""))
    stats = "".join(f'<div class="stat {css}"><div class="k">{html.escape(k)}</div><div class="v">{html.escape(v)}'
                    "</div></div>" for k, v, css in tiles)

    policies = []
    for defender, entry in run["policies"].items():
        policies.append(f"<b>{html.escape(defender)}</b>&nbsp; {html.escape(_policy_text(entry))}")
    fields = [("Study", html.escape(run["study"])), ("World", html.escape(run["world"])),
              ("Evaluation", html.escape(_where(run))),
              ("Mask", html.escape(run.get("mask") or "none")),
              ("Policies", "<br>".join(policies)),
              ("Episode", f"{record.episode} of evaluation seed {record.evaluation_seed}")]
    rows = "".join(f'<div class="field"><div class="name">{name}:</div><div class="value">{value}</div></div>'
                   for name, value in fields)

    title = f"<h1>{html.escape(_heading(record, run))}</h1>" if heading else ""
    top = (f'<header class="top"><div>{title}<div class="fields">{rows}</div></div>'
           f'<div class="stats">{stats}</div></header>')
    return top + _story(record, run, metrics)


def _story(record: EpisodeRecord, run: dict, metrics: dict | None) -> str:

    intrusion = record.script["intrusion"]
    sentences = []

    if intrusion is None:
        sentences.append("No external intrusion in this episode.")
    else:
        sentence = f"Intrusion on {intrusion['server']} at the start of interval {intrusion['interval']}."
        if metrics is not None:
            server = metrics["relevant_b_server"]
            sentence += f" The relevant B server is {server}, the relevant A server {metrics['relevant_a_server']}."
            if metrics["b_no_response"] == "1":
                sentence += f" <b>B</b> never started Inspect, Isolate or Restore on {server} after the intrusion."
            else:
                warned = "a warning" if metrics["b_first_response_warning"] == "1" else "no warning"
                sentence += (f" <b>B</b>'s first response after the intrusion was {metrics['b_first_response_action']}"
                             f" on {server} at interval {metrics['b_first_response_interval']}; at that choice B's"
                             f" observation showed {warned} about {server} and inspection finding"
                             f" {metrics['b_first_response_finding']}.")
        sentences.append(sentence)

    for defender, server, restored_at, warned_at in _restores_on_false_warnings(record):
        sentences.append(f"<b>{defender}</b> restored {server} at interval {restored_at} while its latest warning "
                         f"about it was false, received in interval {warned_at}; {server} was clean.")

    paragraphs = []
    for text in sentences:
        paragraphs.append(f"<p>{text}</p>")
    measured = "" if metrics is None else _measured(run, metrics)
    return f'<div class="story">{"".join(paragraphs)}{measured}</div>'



PAGE_LINES = {
    "b_infected_end": "Episode ends with an infected B server",
    "b_unprompted_enabled": "B's first action on the attacked pair's server came without a warning or an infected "
                            "finding of its own, while that server's monitoring was on",
    "b_unprompted_missed": "B's first action on the attacked pair's server came without a warning or an infected "
                           "finding of its own, while that server's monitoring had missed the intrusion",
    "b_acts_on_peer_failure": "Right after a request to the partner failed, B inspected, isolated or restored a "
                              "running, connected server",
    "a_interrupt_relevant": "A interrupted the attacked pair's server after the intrusion",
    "a_interrupt_relevant_b_closed": "When A first interrupted the attacked pair's server, B's server of the pair was "
                                     "already infected or already patched",
    "a_interrupt_on_evidence_infected": "After a warning or an infected finding about a server that was in truth "
                                        "infected, A interrupted that server",
    "a_interrupt_on_evidence_clean": "After a warning or an infected finding about a server that was in truth clean, "
                                     "A interrupted that server",
    "a_interrupt_b_unaware": "When A first interrupted the attacked pair's server while B's server of the pair was "
                             "still running and connected, B had no warning and no infected finding of its own about "
                             "that server",
    "b_responds_to_a": "B responded to A's interruption of the attacked pair's server",
}


def _episode_name(row: dict) -> str:

    if row["id"] in PAGE_LINES:
        return PAGE_LINES[row["id"]]
    name = row["plain_name"]
    for suffix in (" per intrusion episode", " per episode"):
        name = name.replace(suffix, "")
    return name[0].upper() + name[1:]


def _measured(run: dict, metrics: dict) -> str:

    sender = metrics["a_restores_eligible"] != ""
    parts = []
    for row in base_rows(sender):
        id = row["id"]
        if row["kind"] == EPISODE_INDICATOR and metrics[f"{id}_eligible"] == "1":
            answer = "Yes" if float(metrics[id]) == 1 else "No"
            parts.append(f"<div>{html.escape(_episode_name(row))}: <b>{answer}</b></div>")
        elif row["kind"] in EPISODE_KINDS and metrics[f"{id}_eligible"] == "1":
            parts.append(f"<div>{html.escape(_episode_name(row))}: <b>{float(metrics[id]):g}</b></div>")
        elif row["kind"] in COUNT_KINDS and metrics[f"{id}_denominator"] not in ("", "0"):
            parts.append(f"<div>{html.escape(_episode_name(row))}: <b>{metrics[f'{id}_numerator']}</b> of "
                         f"{metrics[f'{id}_denominator']} times</div>")
    return f'<div class="measured">{"".join(parts)}</div>'


def _restores_on_false_warnings(record: EpisodeRecord) -> list[tuple[str, str, int, int]]:

    latest_warning = {}
    found = []
    for t, interval in enumerate(record.intervals):
        for defender, entry in interval["defenders"].items():
            if entry["free"] and entry["action"] == "restore" and entry["result"] == "accepted":
                warning = latest_warning.get((defender, entry["target"]))
                if not entry["target_at_start"]["compromised"] and warning is not None and warning[1]:
                    found.append((defender, entry["target"], t, warning[0]))

        for defender, delivered in interval["deliveries"].items():
            for server in delivered:
                latest_warning[(defender, server)] = (t, not interval["servers"][server]["compromised"])

    return found


def _outage_cells(record: EpisodeRecord) -> set[tuple[str, int]]:
    cells = set()
    for outage in record.script["outages"]:
        for interval in range(outage["interval"], outage["interval"] + outage["duration"]):
            cells.add((outage["server"], interval))
    return cells


def _legend() -> str:
    
    def swatch(colour=None, css=""):
        style = f' style="background:{colour}"' if colour else ""
        return f'<i class="swatch {css}"{style}></i>'

    def key(title, entries):
        rows = []
        for entry in entries:
            rows.append(f"<tr><td>{entry}</td></tr>")
        return f'<table class="key"><tr><th>{title}</th></tr>{"".join(rows)}</table>'

    states = [f'{swatch(STATE_COLOURS["clean"])}clean',
              f'{swatch(STATE_COLOURS["compromised"])}infected',
              f'{swatch(css="isolated")}isolated',
              f'{swatch(css="stopped")}service stopped',
              f'{swatch(css="patched")}patched',
              f'{swatch(css="outage")}outage (down by itself)']
    events = ["&#9889; intrusion from outside",
              "&#8672; infected by spread",
              "&#128276; warning reaches the defender",
              "&#128277; false warning (the server is clean)",
              "&#128269; inspection result",
              '<span style="color:#b91c1c">&#10006; failed request (world state)</span>']
    actions = []
    for action, colour in ACTION_COLOURS.items():
        actions.append(f"{swatch(colour)}{action}")
    actions.append(f'{swatch(css="first")}B\'s first response after the intrusion')
    actions.append("&middot; wait (no-op)")
    actions.append("&#9702; isolate or reconnect of a server already in that state, so nothing changed")

    return f'<div class="legend">{key("server", states)}{key("events", events)}{key("defender", actions)}</div>'


def _grid(record: EpisodeRecord, run: dict, metrics: dict | None) -> str:

    world = run["settings"]["world"]
    intervals = record.intervals
    employees = {}
    for defender, zone in world["zones"].items():
        employees[zone["employee"]] = defender
    intrusion = record.script["intrusion"]
    intrusion_t = None if intrusion is None else intrusion["interval"]

    spread_targets = {}
    infected_by = {}
    for t, interval in enumerate(intervals):
        spread_targets.update(interval["attacks_started"])
        for source, outcome in interval["attack_completions"].items():
            if outcome == "succeeded":
                infected_by[(t, spread_targets[source])] = source

    finished = {}
    current = {}
    for t, interval in enumerate(intervals):
        for defender, entry in interval["defenders"].items():
            if entry["free"] and entry["result"] == "accepted" and entry["action"] != "wait":
                current[defender] = (entry["action"], entry["target"])
            if entry["completed"]:
                finished[(t, defender)] = current.get(defender, (entry["completed"], None))

    first_response = None
    if metrics is not None and metrics["b_first_response_interval"] != "":
        first_response = (int(metrics["b_first_response_interval"]), metrics["b_first_response_action"],
                          metrics["relevant_b_server"])

    header = []
    for t in range(len(intervals)):
        css = "intrusion" if t == intrusion_t else "interval"
        title = f"intrusion on {intrusion['server']} at the start of interval {t}" if t == intrusion_t else f"interval {t}"
        header.append(f'<th class="{css}" title="{html.escape(title)}">{t}</th>')
    rows = ['<tr><th class="label">interval</th>' + "".join(header) + "</tr>"]

    for defender, zone in world["zones"].items():
        rows.append(f'<tr class="zone"><td class="label">zone {html.escape(defender)} &middot; employee '
                    f'{html.escape(zone["employee"])}</td>' + '<td class="fill"></td>' * len(intervals) + "</tr>")
        for server in zone["servers"]:
            rows.append(_server_row(server, defender, record, intrusion, infected_by, finished, employees))
        rows.append(_defender_row(defender, record, intrusion_t, first_response if defender == "B" else None))

    rows.extend(_reward_rows(record, intrusion_t))
    return '<div class="grid-wrap"><table class="grid">' + "".join(rows) + "</table></div>"


def _server_row(server, defender, record, intrusion, infected_by, finished, employees) -> str:
    cells = [f'<td class="label">{html.escape(server)}</td>']
    intrusion_t = None if intrusion is None else intrusion["interval"]
    outages = _outage_cells(record)

    for t, interval in enumerate(record.intervals):
        state = interval["servers"][server]
        classes = ["server", "isolated" if state["isolated"] else "", "stopped" if not state["service_running"] else "",
                   "patched" if not state["vulnerable"] else "", "col-intrusion" if t == intrusion_t else ""]
        colour = STATE_COLOURS["compromised" if state["compromised"] else "clean"]
        marks = []
        notes = [f"{server}, end of interval {t}: " + ", ".join(
            word for word, flag in (("INFECTED", state["compromised"]), ("clean", not state["compromised"]),
                                    ("isolated", state["isolated"]), ("service stopped", not state["service_running"]),
                                    ("patched", not state["vulnerable"])) if flag)]
        if interval["intrusion"] == server:
            marks.append("&#9889;")
            notes.append("intrusion from outside")
        if (t, server) in infected_by:
            marks.append("&#8672;")
            notes.append(f"infected by spread from {infected_by[(t, server)]}")
        if server in interval["deliveries"].get(defender, {}):
            
            if state["compromised"]:
                marks.append("&#128276;")
                notes.append(f"warning about {server} reaches defender {defender} (seen from the next boundary)")
            else:
                marks.append("&#128277;")
                notes.append(f"false warning about {server} reaches defender {defender}, {server} is clean "
                             "(seen from the next boundary)")
        if (server, t) in outages:
            classes.append("outage")
            notes.append(f"outage: {server} is down by itself")
        if finished.get((t, defender)) == ("inspect", server):
            observed = record.boundaries[t + 1]["observations"][defender]["servers"][server]
            marks.append("&#128269;")
            notes.append(f"inspection of {server} finished: {FINDINGS[observed['inspection_finding']]}")
        failed = []
        for source, target, succeeded in interval["requests"]:
            if not succeeded and (source == server or (target == server and employees.get(source) == defender)):
                failed.append(f"{source}→{target}")
        if failed:
            marks.append('<span style="color:#b91c1c">&#10006;</span>')
            notes.append("failed requests involving this server: " + ", ".join(failed))
        cells.append(f'<td class="{" ".join(c for c in classes if c)}" style="background-color:{colour}" '
                     f'title="{html.escape(chr(10).join(notes))}">{"".join(marks[:2])}</td>')
    return "<tr>" + "".join(cells) + "</tr>"


def _defender_row(defender, record, intrusion_t, first_response) -> str:
    cells = [f'<td class="label defender-label">defender {html.escape(defender)} &middot; actions</td>']
    intervals = record.intervals
    t = 0
    while t < len(intervals):
        entry = intervals[t]["defenders"][defender]
        column = " col-intrusion" if t == intrusion_t else ""
        if not entry["free"]:
            cells.append(f'<td class="wait{column}" title="busy, its job continues"></td>')
            t += 1
            continue
        action, target, result = entry["action"], entry["target"], entry["result"]
        seen = _observation_text(record.boundaries[t]["observations"][defender])
        title = html.escape(f"interval {t}: chose {action}{' ' + target if target else ''} ({result})\n\n"
                            f"what it saw at the start:\n{seen}")
        if action == "wait":
            cells.append(f'<td class="wait{column}" title="{title}">&middot;</td>')
            t += 1
            continue
        if result != "accepted":
            cells.append(f'<td class="noop{column}" title="{title}">&#9702;</td>')
            t += 1
            continue
        span = 1
        while t + span < len(intervals) and not intervals[t + span]["defenders"][defender]["free"]:
            span += 1
        first = first_response == (t, action, target)
        label = html.escape(f"{action} {target}" if span >= 3 else SHORT_LABELS[action])
        if first:
            label = "&#9733; " + label
        cells.append(f'<td class="action{" first" if first else ""}" colspan="{span}" '
                     f'style="background:{ACTION_COLOURS[action]}" title="{title}">{label}</td>')
        t += span
    return "<tr>" + "".join(cells) + "</tr>"


def _observation_text(observed: dict) -> str:

    own = []
    for name in ("elapsed_steps", "extra_detector_available", "job_action", "job_target", "job_remaining_steps",
                 "last_command_feedback"):
        own.append(f"{name.replace('_', ' ')} {observed[name]}")
    lines = ["own: " + ", ".join(own)]
    for server, shown in observed["servers"].items():
        parts = ["running" if shown["service_running"] == 1 else "service stopped"]
        if shown["isolated"] == 1:
            parts.append("isolated")
        parts.append(f"employee request {PEER_RESULTS[shown['employee_request_result']]}")
        parts.append(f"peer request {PEER_RESULTS[shown['peer_request_result']]}")
        parts.append(f"inspection finding {FINDINGS[shown['inspection_finding']]}")
        if shown["inspection_age"] >= 0:
            parts.append(f"inspection age {shown['inspection_age']}")
        if shown["warning_received"] == 1:
            parts.append(f"open warning, age {shown['warning_age']}")
        lines.append(f"{server}: " + ", ".join(parts))
    return "\n".join(lines)


def _reward_rows(record: EpisodeRecord, intrusion_t) -> list[str]:
    cells = ['<td class="label">shared reward</td>']
    totals = ['<td class="label">running total</td>']
    running = 0.0
    worst = 0.0
    for interval in record.intervals:
        worst = min(worst, interval["reward"]["shared"])
    for t, interval in enumerate(record.intervals):
        reward = interval["reward"]
        running += reward["shared"]
        strength = 0.0 if worst >= 0 else min(1.0, reward["shared"] / worst)
        colour = f"rgba(185,28,28,{0.10 + 0.55 * strength:.2f})" if reward["shared"] < 0 else "#f3f4f6"
        column = " col-intrusion" if t == intrusion_t else ""
        costs = ", ".join(f"{zone} {cost:g}" for zone, cost in reward["compromise_cost_by_zone"].items())
        title = (f"interval {t}: reward {reward['shared']:g}; {reward['compromised_server_count']} infected, "
                 f"compromise cost by zone {costs}; {reward['failed_request_count']} failed requests; "
                 f"{reward['inspection_start_count']} inspections started")
        cells.append(f'<td class="reward{column}" style="background:{colour}" title="{html.escape(title)}">'
                     f'{reward["shared"]:g}</td>')
        totals.append(f'<td class="running{column}" title="running total after interval {t}">{running:g}</td>')
    return ["<tr>" + "".join(cells) + "</tr>", "<tr>" + "".join(totals) + "</tr>"]


def main(arguments: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Write one evaluation episode as an HTML timeline.")
    parser.add_argument("folder", help="an evaluation folder in runs/, holding run.json and records.jsonl.gz")
    parser.add_argument("--seed", type=int, required=True, help="the evaluation seed, 2001 or 2002")
    parser.add_argument("--episode", type=int, required=True, help="the episode's index within its evaluation seed")
    parser.add_argument("--episodes", help="that evaluation's episodes.csv, for the story and the measurements")
    parser.add_argument("--out", help="the page to write (default: timelines/ in the evaluation folder)")
    options = parser.parse_args(arguments)

    folder = Path(options.folder)
    run = read_run_json(folder / "run.json")
    found = None
    for record in read_records(folder / "records.jsonl.gz"):
        if record.evaluation_seed == options.seed and record.episode == options.episode:
            found = record
            break
    if found is None:
        parser.error(f"{folder} holds no episode {options.episode} of evaluation seed {options.seed}")

    metrics = None
    if options.episodes is not None:
        with Path(options.episodes).open(newline="") as file:
            for row in csv.DictReader(file):
                if row["evaluation_seed"] == str(options.seed) and row["episode"] == str(options.episode):
                    metrics = row

    out = Path(options.out) if options.out else folder / "timelines" / f"episode-{options.seed}-{options.episode:03d}.html"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(timeline_html(found, run, metrics))
    print(out)


if __name__ == "__main__":
    main()
