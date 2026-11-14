from episodes.record import EpisodeRecord, relevant_servers
from measurements.decisions import peer_failure_decisions
from measurements.facts import (
    RESPONSES,
    check_record,
    finding,
    no_own_evidence,
    shown,
    started,
    warning,
)
from measurements.glossary import BASE, COUNT_KINDS, EPISODE_KINDS
from measurements.interruptions import interruptions_of
from measurements.opportunities import OPPORTUNITY_CLASS, opportunities_of

EPISODE_IDS = []
COUNT_IDS = []
SENDER_EPISODE_IDS = []
SENDER_COUNT_IDS = []


for _row in BASE:
    
    if _row["kind"] in EPISODE_KINDS:
        EPISODE_IDS.append(_row["id"])
        if _row["studies"] == "sender":
            SENDER_EPISODE_IDS.append(_row["id"])
            
    if _row["kind"] in COUNT_KINDS:
        COUNT_IDS.append(_row["id"])
        if _row["studies"] == "sender":
            SENDER_COUNT_IDS.append(_row["id"])



SCRIPT_COLUMNS = ["intrusion_server", 
                  "intrusion_interval", 
                  "false_warnings", 
                  "missed_servers", 
                  "outages",
                  "relevant_a_server", 
                  "relevant_b_server", 
                  "relevant_b_monitoring_missed"]


FIRST_RESPONSE_COLUMNS = ["b_first_response_interval", 
                          "b_first_response_action", 
                          "b_first_response_warning",
                          "b_first_response_finding", 
                          "b_no_response"]



def episode_columns(world: dict) -> list[str]:
    
    columns = ["episode", "evaluation_seed", "iteration"] + SCRIPT_COLUMNS
    
    for id in EPISODE_IDS:
        columns.append(id)
        columns.append(f"{id}_eligible")
        
    for id in COUNT_IDS:
        columns.append(f"{id}_numerator")
        columns.append(f"{id}_denominator")
        
    columns.extend(FIRST_RESPONSE_COLUMNS)
    
    for server in world["zones"]["B"]["servers"]:
        columns.append(f"final_compromised_{server}")
        
        
    return columns




def script_columns(record: EpisodeRecord, world: dict) -> dict:
    
    script = record.script
    intrusion = script["intrusion"]
    relevant = relevant_servers(record, world)

    false_warnings = []
    for false_warning in script["false_warnings"]:
        false_warnings.append(f"{false_warning['server']}@{false_warning['interval']}")
        
    outages = []
    for outage in script["outages"]:
        outages.append(f"{outage['server']}@{outage['interval']}+{outage['duration']}")

    return {"intrusion_server": None if intrusion is None else intrusion["server"],
            "intrusion_interval": None if intrusion is None else intrusion["interval"],
            "false_warnings": ";".join(false_warnings),
            "missed_servers": ";".join(script["missed_servers"]),
            "outages": ";".join(outages),
            "relevant_a_server": None if relevant is None else relevant["A"],
            "relevant_b_server": None if relevant is None else relevant["B"],
            "relevant_b_monitoring_missed": None if relevant is None else int(relevant["B"] in script["missed_servers"])}



def first_response(record: EpisodeRecord, server: str, intrusion_interval: int) -> int | None:

    for t in range(intrusion_interval + 1, len(record.intervals)):
        
        entry = record.intervals[t]["defenders"]["B"]
        if started(entry, RESPONSES) and entry["target"] == server:
            return t
        
    return None



def measure_episode(record: EpisodeRecord, world: dict, sender: bool) -> dict:
    
    check_record(record, world)
    
    intrusion = record.script["intrusion"]
    relevant = relevant_servers(record, world)
    intruded = intrusion is not None
    
    a_servers = world["zones"]["A"]["servers"]
    b_servers = world["zones"]["B"]["servers"]
    
    final = record.intervals[-1]["servers"]

    row = {"episode": record.episode, "evaluation_seed": record.evaluation_seed, "iteration": record.iteration}
    row.update(script_columns(record, world))

    reward = 0.0
    failed = 0
    for t, interval in enumerate(record.intervals):
        
        reward += interval["reward"]["shared"]
        failed_here = 0
        
        for _source, _target, succeeded in interval["requests"]:
            if not succeeded:
                failed_here += 1
                
        if failed_here != interval["reward"]["failed_request_count"]:
            raise ValueError(f"episode {record.episode}, interval {t}: {failed_here} failed requests in the request list, {interval['reward']['failed_request_count']} in the reward")
            
        failed += failed_here


    _put(row, "reward", reward, True)
    _put(row, "b_infected_intervals", _infected_intervals(record, b_servers), intruded)
    _put(row, "b_infected_end", int(any(final[server]["compromised"] for server in b_servers)), intruded)
    _put(row, "failed_requests", failed, True)
    _put(row, "inspections_a", _starts(record, "A", "inspect"), True)
    _put(row, "inspections_b", _starts(record, "B", "inspect"), True)

    # B's first response on the relevant server.
    response = None
    unprompted = None
    missed = None
    
    if intruded:
        response = first_response(record, relevant["B"], intrusion["interval"])
        unprompted = 0 if response is None else int(no_own_evidence(shown(record, response, "B", relevant["B"])))
        missed = relevant["B"] in record.script["missed_servers"]
        
        
    _put(row, "b_unprompted_enabled", unprompted, intruded and not missed)
    _put(row, "b_unprompted_missed", unprompted, intruded and missed)

    _put(row, "clean_restores_b", _clean_restores(record, "B"), True)
    _put(row, "clean_restores_a", _clean_restores(record, "A"), True)

    if sender:
        
        interruptions = interruptions_of(record, world)
        relevant_rows = []
        clean = 0
        
        for interruption in interruptions:
            if interruption["relevant"]:
                relevant_rows.append(interruption)
            if not interruption["target_compromised_at_start"]:
                clean += 1
                
        observable = None
        
        for interruption in relevant_rows:
            if interruption["observable"]:
                observable = interruption
                break
            
        first = relevant_rows[0] if relevant_rows else None

        _put(row, "a_restores", _starts(record, "A", "restore"), True)
        _put(row, "a_isolates", _starts(record, "A", "isolate"), True)
        _put(row, "a_interrupts", len(interruptions), True)
        _put(row, "a_interrupt_relevant", int(first is not None), intruded)
        
        _put(row, "a_interrupt_relevant_b_closed",
             None if first is None else int(first["paired_b_compromised_at_start"] or first["paired_b_patched_at_start"]),
             first is not None)
        
        _put(row, "a_interrupts_clean", clean, True)
        
        _put(row, "a_interrupt_b_unaware",
             None if observable is None else int(no_own_evidence(shown(record, observable["interval"] + 1, "B",
                                                                       observable["paired_b_server"]))),
             observable is not None)
        
        _put(row, "a_infected_intervals", _infected_intervals(record, a_servers), intruded)

        responded = 0
        eligible = 0
        for interruption in relevant_rows:
            if interruption["b_responds_eligible"]:
                eligible += 1
                responded += interruption["b_responds"]
                
        _count(row, "b_responds_to_a", responded, eligible)

        opportunities = opportunities_of(record, world)
        for id, status in OPPORTUNITY_CLASS.items():
            scored = 0
            total = 0
            for opportunity in opportunities:
                if opportunity["status"] == status:
                    total += 1
                    scored += opportunity["score"]
            _count(row, id, scored, total)
            
            
    else:
        for id in SENDER_EPISODE_IDS:
            row[id] = None
            row[f"{id}_eligible"] = None
            
        for id in SENDER_COUNT_IDS:
            row[f"{id}_numerator"] = None
            row[f"{id}_denominator"] = None


    if response is None:
        row.update({"b_first_response_interval": None, 
                    "b_first_response_action": None,
                    "b_first_response_warning": None, 
                    "b_first_response_finding": None,
                    "b_no_response": 1 if intruded else None})
        
    else:
        observed = shown(record, response, "B", relevant["B"])
        row.update({"b_first_response_interval": response,
                    "b_first_response_action": record.intervals[response]["defenders"]["B"]["action"],
                    "b_first_response_warning": int(warning(observed)),
                    "b_first_response_finding": finding(observed),
                    "b_no_response": 0})


    decisions, qualifying = peer_failure_decisions(record, world)
    _count(row, "b_acts_on_peer_failure", qualifying, decisions)

    for server in b_servers:
        row[f"final_compromised_{server}"] = int(final[server]["compromised"])

    return row


def _put(row: dict, id: str, value, eligible: bool) -> None:

    row[id] = value if eligible else None
    row[f"{id}_eligible"] = int(eligible)


def _count(row: dict, id: str, numerator: int, denominator: int) -> None:
    row[f"{id}_numerator"] = numerator
    row[f"{id}_denominator"] = denominator


def _infected_intervals(record: EpisodeRecord, servers: list[str]) -> int:
    count = 0
    for interval in record.intervals:
        for server in servers:
            if interval["servers"][server]["compromised"]:
                count += 1
    return count


def _starts(record: EpisodeRecord, defender: str, action: str) -> int:
    count = 0
    for interval in record.intervals:
        if started(interval["defenders"][defender], (action,)):
            count += 1
    return count


def _clean_restores(record: EpisodeRecord, defender: str) -> int:

    count = 0
    for interval in record.intervals:
        entry = interval["defenders"][defender]
        if started(entry, ("restore",)) and not entry["target_at_start"]["compromised"]:
            count += 1
    return count
