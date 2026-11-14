from episodes.record import EpisodeRecord

ACTIONS = (None, "wait", "inspect", "isolate", "restore", "reconnect")
RESULTS = (None, "accepted", "already_satisfied", "rejected")


RESPONSES = ("inspect", "isolate", "restore")

#observations
FLAGS = {0: False, 1: True}
FINDINGS = {-1: "unknown", 0: "clean", 1: "infected"}
PEER_RESULTS = {-1: "unknown", 0: "failed", 1: "succeeded"}

#validate
def check_record(record: EpisodeRecord, world: dict) -> None:

    if set(world["zones"]) != {"A", "B"}:
        raise ValueError(f"the measurements need the zones A and B, not {sorted(world['zones'])}")

    steps = world["episode"]["max_steps"]
    if len(record.intervals) != steps or len(record.boundaries) != steps + 1:
        raise ValueError(f"episode {record.episode} has {len(record.intervals)} intervals and {len(record.boundaries)} boundaries; the world's episodes have {steps} intervals")

    for t, interval in enumerate(record.intervals):
        
        for defender in ("A", "B"):
            entry = interval["defenders"][defender]
            
            if entry["action"] not in ACTIONS or entry["result"] not in RESULTS:
                raise ValueError(f"episode {record.episode}, interval {t}, defender {defender}: unknown action or result in {entry}")
            
            if entry["free"] != (entry["action"] is not None) or entry["free"] != (entry["result"] is not None):
                raise ValueError(f"episode {record.episode}, interval {t}, defender {defender}: free, action and result disagree in {entry}")


#hidden truth.
def truth(record: EpisodeRecord, boundary: int, server: str) -> dict:
    if boundary == 0:
        return record.initial_servers[server]
    return record.intervals[boundary - 1]["servers"][server]


#what observation vector shows.
def shown(record: EpisodeRecord, boundary: int, defender: str, server: str) -> dict:
    return record.boundaries[boundary]["observations"][defender]["servers"][server]


def warning(observed: dict) -> bool:
    return FLAGS[observed["warning_received"]]


def finding(observed: dict) -> str:
    return FINDINGS[observed["inspection_finding"]]


def peer_result(observed: dict) -> str:
    return PEER_RESULTS[observed["peer_request_result"]]


def shown_available(observed: dict) -> bool:
    return FLAGS[observed["service_running"]] and not FLAGS[observed["isolated"]]


def no_own_evidence(observed: dict) -> bool:
    return not warning(observed) and finding(observed) in ("clean", "unknown")


#accepted action job started.
def started(entry: dict, actions: tuple[str, ...]) -> bool:
    return entry["result"] == "accepted" and entry["action"] in actions



def partners(world: dict) -> dict[str, str]:
    
    result = {}
    
    for first, second in world["network"]["server_pairs"]:
        result[first] = second
        result[second] = first
        
    return result
