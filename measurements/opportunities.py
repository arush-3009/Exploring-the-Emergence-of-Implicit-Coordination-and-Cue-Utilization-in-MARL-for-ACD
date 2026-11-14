from episodes.record import EpisodeRecord, available
from measurements.facts import check_record, finding, partners, shown, truth, warning
from measurements.interruptions import is_interruption

OPPORTUNITY_COLUMNS = ["episode", 
                       "evaluation_seed", 
                       "iteration",
                       "server", 
                       "boundary",
                       "status",
                       "a_warning",
                       "a_finding", 
                       "close_interval", 
                       "close_event",
                       "first_interruption_interval", 
                       "score"]


OPPORTUNITY_CLASS = {"a_interrupt_on_evidence_infected": "infected", 
                     "a_interrupt_on_evidence_clean": "clean"}


# Inside an interval an intrusion comes before 
# the defenders' starts; a completed Restore and 
# a succeeded spread come after them.
BEFORE_STARTS = 0
AFTER_STARTS = 1


def infection_changes(record: EpisodeRecord, world: dict) -> dict[str, list[tuple[int, int, str]]]:

    partner = partners(world)
    servers = list(world["zones"]["A"]["servers"]) + list(world["zones"]["B"]["servers"])

    status = {}
    changes = {}
    for server in servers:
        status[server] = record.initial_servers[server]["compromised"]
        changes[server] = []

    job_target = {"A": None, "B": None}
    
    for t, interval in enumerate(record.intervals):

        intruded = interval["intrusion"]
        if intruded is not None and not status[intruded]:
            status[intruded] = True
            changes[intruded].append((t, BEFORE_STARTS, "intrusion"))

        for defender in ("A", "B"):
            entry = interval["defenders"][defender]
            if entry["result"] == "accepted" and entry["action"] != "wait":
                job_target[defender] = entry["target"]

        for defender in ("A", "B"):
            if interval["defenders"][defender]["completed"] == "restore":
                server = job_target[defender]
                if status[server]:
                    status[server] = False
                    changes[server].append((t, AFTER_STARTS, "restore"))

        for source, outcome in interval["attack_completions"].items():
            if outcome == "succeeded":
                server = partner[source]
                if status[server]:
                    raise ValueError(f"episode {record.episode}, interval {t}: a spread succeeded into {server}, which the replay already has infected")
                status[server] = True
                changes[server].append((t, AFTER_STARTS, "spread"))

        for server in servers:
            if status[server] != interval["servers"][server]["compromised"]:
                raise ValueError(f"episode {record.episode}, interval {t}: the replayed infection of {server} does not match the recorded truth")


    return changes

# first boundary at which A is free to choose 
# and its observation shows a visible warning or 
# an infected inspection finding for this server, while
# the server is running and not isolated in hidden truth.
def opportunity_boundary(record: EpisodeRecord, server: str) -> int | None:

    for boundary in range(len(record.intervals)):
        
        if not record.intervals[boundary]["defenders"]["A"]["free"]:
            continue
        
        observed = shown(record, boundary, "A", server)
        
        if (warning(observed) or finding(observed) == "infected") and available(truth(record, boundary, server)):
            return boundary
        
    return None



def opportunities_of(record: EpisodeRecord, world: dict) -> list[dict]:

    check_record(record, world)
    
    changes = infection_changes(record, world)

    rows = []
    for server in world["zones"]["A"]["servers"]:
        boundary = opportunity_boundary(record, server)
        if boundary is None:
            continue

        close = None
        for change in changes[server]:
            if change[0] >= boundary:
                close = change
                break

        first = None
        for t in range(boundary, len(record.intervals)):
            if close is not None and (t > close[0] or (t == close[0] and close[1] == BEFORE_STARTS)):
                break
            
            entry = record.intervals[t]["defenders"]["A"]
            
            if is_interruption(entry) and entry["target"] == server:
                first = t
                break

        observed = shown(record, boundary, "A", server)
        
        rows.append({"episode": record.episode,
                     "evaluation_seed": record.evaluation_seed,
                     "iteration": record.iteration,
                     "server": server,
                     "boundary": boundary,
                     "status": "infected" if truth(record, boundary, server)["compromised"] else "clean",
                     "a_warning": int(warning(observed)),
                     "a_finding": finding(observed),
                     "close_interval": None if close is None else close[0],
                     "close_event": "episode end" if close is None else close[2],
                     "first_interruption_interval": first,
                     "score": int(first is not None)})

    return rows
