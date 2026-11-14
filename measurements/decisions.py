#b_acts_on_peer_failure's two counts for one episode.

from episodes.record import EpisodeRecord
from measurements.facts import RESPONSES, peer_result, shown, shown_available, started


# A free decision is eligible when B's pre-choice 
# observation, masks included, shows at least one local 
# server with a failed peer request, running service and 
# no isolation. It qualifies when B starts an accepted Inspect, 
# Isolate or Restore on one of exactly those servers. Busy intervals 
# and the final boundary, which has no choice, are not decisions; each 
# decision counts at most once, however many servers qualify.
def peer_failure_decisions(record: EpisodeRecord, world: dict) -> tuple[int, int]:
   
    eligible = 0
    qualifying = 0

    for t, interval in enumerate(record.intervals):
        entry = interval["defenders"]["B"]
        if not entry["free"]:
            continue

        targets = []
        for server in world["zones"]["B"]["servers"]:
            observed = shown(record, t, "B", server)
            if peer_result(observed) == "failed" and shown_available(observed):
                targets.append(server)
        if not targets:
            continue

        eligible += 1
        if started(entry, RESPONSES) and entry["target"] in targets:
            qualifying += 1

    return eligible, qualifying
