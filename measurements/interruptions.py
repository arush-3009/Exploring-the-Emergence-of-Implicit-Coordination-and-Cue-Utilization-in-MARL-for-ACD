from episodes.record import EpisodeRecord, available, relevant_servers
from measurements.facts import (
    RESPONSES,
    check_record,
    finding,
    partners,
    peer_result,
    shown,
    shown_available,
    started,
    truth,
    warning,
)

# Filled only for a relevant interruption
RESPONSE_COLUMNS = ["window_last_boundary", 
                    "b_choice_boundary", 
                    "paired_b_available_at_choice",
                    "b_choice_action", 
                    "b_choice_target", 
                    "b_choice_result", 
                    "delay",
                    "paired_b_warning_after", 
                    "paired_b_finding_after",
                    "paired_b_warning_at_choice", 
                    "paired_b_finding_at_choice",
                    "b_responds_eligible", 
                    "b_responds"]


INTERRUPTION_COLUMNS = ["episode", 
                        "evaluation_seed", 
                        "iteration", 
                        "interval", 
                        "target", 
                        "action",
                        "target_compromised_at_start", 
                        "a_warning", 
                        "a_finding", 
                        "paired_b_server",
                        "paired_b_compromised_at_start", 
                        "paired_b_patched_at_start",
                        "paired_b_running_at_requests", 
                        "paired_b_isolated_at_requests",
                        "observable", 
                        "b_shown_failure", 
                        "relevant"] + RESPONSE_COLUMNS




def is_interruption(entry: dict) -> bool:
    return started(entry, ("restore", "isolate")) and available(entry["target_at_start"])



def window(record: EpisodeRecord, t: int, a_server: str) -> range:

    steps = len(record.intervals)
    stop = steps
    
    for boundary in range(t + 2, steps):
        if available(truth(record, boundary, a_server)):
            stop = boundary
            break
    
    return range(t + 1, stop)



def status_at_start(record: EpisodeRecord, t: int, server: str) -> tuple[bool, bool]:
    before = truth(record, t, server)
    compromised = before["compromised"] or record.intervals[t]["intrusion"] == server
    return compromised, not before["vulnerable"]




def interruptions_of(record: EpisodeRecord, world: dict) -> list[dict]:
    
    check_record(record, world)
    
    intrusion = record.script["intrusion"]
    relevant = relevant_servers(record, world)
    partner = partners(world)

    rows = []
    for t, interval in enumerate(record.intervals):
        
        entry = interval["defenders"]["A"]
        if not is_interruption(entry):
            continue

        target = entry["target"]
        paired = partner[target]
        
        seen_by_a = shown(record, t, "A", target)
        
        compromised, patched = status_at_start(record, t, paired)
        
        at_requests = interval["servers"][paired]
        is_relevant = relevant is not None and target == relevant["A"] and t > intrusion["interval"]

        row = {"episode": record.episode,
               "evaluation_seed": record.evaluation_seed,
               "iteration": record.iteration,
               "interval": t,
               "target": target,
               "action": entry["action"],
               "target_compromised_at_start": int(entry["target_at_start"]["compromised"]),
               "a_warning": int(warning(seen_by_a)),
               "a_finding": finding(seen_by_a),
               "paired_b_server": paired,
               "paired_b_compromised_at_start": int(compromised),
               "paired_b_patched_at_start": int(patched),
               "paired_b_running_at_requests": int(at_requests["service_running"]),
               "paired_b_isolated_at_requests": int(at_requests["isolated"]),
               "observable": int(available(at_requests)),
               "b_shown_failure": int(peer_result(shown(record, t + 1, "B", paired)) == "failed"),
               "relevant": int(is_relevant)}

        if is_relevant:
            row.update(response_to(record, t, target, paired))
        else:
            for column in RESPONSE_COLUMNS:
                row[column] = None
                
        rows.append(row)

    return rows


def response_to(record: EpisodeRecord, t: int, a_server: str, b_server: str) -> dict:

    boundaries = window(record, t, a_server)
    after = shown(record, t + 1, "B", b_server)

    choice = None
    for boundary in boundaries:
        if record.intervals[boundary]["defenders"]["B"]["free"]:
            choice = boundary
            break

    row = {"window_last_boundary": boundaries[-1] if boundaries else None,
           "b_choice_boundary": choice,
           "paired_b_warning_after": int(warning(after)),
           "paired_b_finding_after": finding(after)}

    if choice is None:
        for column in ("paired_b_available_at_choice", 
                       "b_choice_action", 
                       "b_choice_target", 
                       "b_choice_result",
                       "delay", 
                       "paired_b_warning_at_choice", 
                       "paired_b_finding_at_choice",
                       "b_responds"):
            
            row[column] = None
            
            
        row["b_responds_eligible"] = 0
        
        return row

    entry = record.intervals[choice]["defenders"]["B"]
    at_choice = shown(record, choice, "B", b_server)
    eligible = shown_available(at_choice)

    row.update({"paired_b_available_at_choice": int(eligible),
                "b_choice_action": entry["action"],
                "b_choice_target": entry["target"],
                "b_choice_result": entry["result"],
                "delay": choice - (t + 1),
                "paired_b_warning_at_choice": int(warning(at_choice)),
                "paired_b_finding_at_choice": finding(at_choice),
                "b_responds_eligible": int(eligible),
                "b_responds": int(started(entry, RESPONSES) and entry["target"] == b_server) if eligible else None})
    
    return row
