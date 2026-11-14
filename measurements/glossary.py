# Every measurement of the experiment used for stats and figures.

from pathlib import Path

from measurements.tables import write_csv

EPISODE_INDICATOR = "episode indicator"  # 0 or 1 per eligible episode
EPISODE_TOTAL = "episode total"
PER_DECISION = "per decision"
PER_INTERRUPTION = "per interruption"
PER_OPPORTUNITY = "per opportunity"
PROBE = "probe"
DIFFERENCE = "difference"
EPISODE_KINDS = (EPISODE_INDICATOR, EPISODE_TOTAL)
COUNT_KINDS = (PER_DECISION, PER_INTERRUPTION, PER_OPPORTUNITY)

MEASUREMENT_COLUMNS = ["id", "long_name", "plain_name", "kind", "population", "denominator", "base_id", "studies"]


def _row(id, long_name, plain_name, kind, population, denominator, studies):
    
    return {"id": id, 
            "long_name": long_name, 
            "plain_name": plain_name, 
            "kind": kind,
            "population": population, 
            "denominator": denominator, 
            "base_id": None, 
            "studies": studies}



BASE = [
    
    _row("reward", "reward", "team reward per episode", EPISODE_TOTAL,
         "all episodes", "number of episodes", "all"),
    
    _row("b_infected_intervals", "b_infected_server_intervals",
         "B's infected server-intervals per intrusion episode", EPISODE_TOTAL,
         "intrusion episodes", "number of intrusion episodes", "all"),
    
    _row("b_infected_end", "b_infected_at_episode_end", "intrusion episodes ending with an infected B server",
         EPISODE_INDICATOR, "intrusion episodes",
         "all intrusion episodes, including those where B never became infected", "all"),
    
    _row("failed_requests", "failed_requests", "failed requests per episode", EPISODE_TOTAL,
         "all episodes", "episodes", "all"),
    
    _row("inspections_a", "inspections_a", "A's inspections per episode", EPISODE_TOTAL,
         "all episodes", "episodes", "all"),
    
    _row("inspections_b", "inspections_b", "B's inspections per episode", EPISODE_TOTAL,
         "all episodes", "episodes", "all"),
    
    _row("b_unprompted_enabled", "b_first_response_without_own_infection_evidence_monitoring_enabled",
         "B's first action on the attacked pair's server came with no warning and no infected finding of its own visible, server monitored",
         EPISODE_INDICATOR,
         "intrusion episodes where the attacked pair's B server has its infection monitoring on",
         "all such episodes, including those where B never acted, had evidence visible, or never got an infection warning",
         "all"),
    
    _row("b_unprompted_missed", "b_first_response_without_own_infection_evidence_monitoring_missed",
         "B's first action on the attacked pair's server came with no warning and no infected finding of its own visible, server's monitoring missed",
         EPISODE_INDICATOR,
         "intrusion episodes where the attacked pair's B server has its infection monitoring missed (random warnings can still arrive)",
         "all such episodes, including those where B never acted or had evidence visible from a random warning or an inspection",
         "all"),
    
    _row("b_acts_on_peer_failure", "b_acts_on_current_peer_failure",
         "B inspected, isolated or restored a running, connected server right after its request to the partner failed",
         PER_DECISION,
         "B's free choices with a running, connected server whose partner request had just failed",
         "all such choices, counted once even if several servers qualify", "all"),
    
    _row("clean_restores_b", "clean_restores_b", "B's restores of clean servers per episode", EPISODE_TOTAL,
         "all episodes", "episodes", "all"),
    
    _row("clean_restores_a", "clean_restores_a", "A's restores of clean servers per episode", EPISODE_TOTAL,
         "all episodes", "episodes", "all"),
    
    _row("a_restores", "a_restore_starts", "A's restores per episode", EPISODE_TOTAL,
         "all episodes", "episodes", "sender"),
    
    _row("a_isolates", "a_isolate_starts", "A's isolations per episode", EPISODE_TOTAL,
         "all episodes", "episodes", "sender"),
    
    _row("a_interrupts", "a_interruptions", "A's interruptions per episode", EPISODE_TOTAL,
         "all episodes", "episodes", "sender"),
    
    _row("a_interrupt_relevant", "a_interrupted_relevant_server_after_intrusion",
         "A interrupted the attacked pair's server after the intrusion", EPISODE_INDICATOR,
         "intrusion episodes", "intrusion episodes", "sender"),
    
    _row("a_interrupt_relevant_b_closed",
         "a_first_relevant_interruption_with_paired_b_server_already_infected_or_patched",
         "when A first interrupted the attacked pair's server, B's server of the pair was already infected or already patched",
         EPISODE_INDICATOR, "intrusion episodes where A interrupted the attacked pair's server after the intrusion",
         "those episodes", "sender"),
    
    _row("a_interrupt_on_evidence_infected", "a_interrupted_after_opportunity_while_server_still_infected",
         "A interrupted a server after a warning or an infected finding about it, while the server was in truth infected",
         PER_OPPORTUNITY,
         "A's first free choices with a warning or an infected finding about one of its available servers, that server in truth infected",
         "all such choices, including those A never acted on before the server's state changed", "sender"),
    
    _row("a_interrupt_on_evidence_clean", "a_interrupted_after_opportunity_while_server_still_clean",
         "A interrupted a server after a warning or an infected finding about it, while the server was in truth clean",
         PER_OPPORTUNITY,
         "A's first free choices with a warning or an infected finding about one of its available servers, that server in truth clean",
         "all such choices, including those A never acted on before the server's state changed", "sender"),
    
    _row("a_interrupts_clean", "a_interruptions_of_clean_servers", "A's interruptions of clean servers per episode",
         EPISODE_TOTAL, "all episodes", "episodes", "sender"),
    
    _row("a_interrupt_b_unaware",
         "a_first_observable_relevant_interruption_with_no_own_infection_evidence_visible_to_b",
         "when A first interrupted the attacked pair's server while B's server of the pair was running and connected, B had no warning and no infected finding of its own visible about that server",
         EPISODE_INDICATOR,
         "intrusion episodes where A interrupted the attacked pair's server while B's server of the pair was running and connected",
         "those episodes", "sender"),
    
    _row("b_responds_to_a", "b_first_free_choice_after_relevant_interruption_acts_on_paired_server",
         "B responded to A's interruption", PER_INTERRUPTION,
         "A's interruptions of the attacked pair's server that B had a free choice to answer in time",
         "those interruptions", "sender"),
    
    _row("a_infected_intervals", "a_infected_server_intervals",
         "A's infected server-intervals per intrusion episode", EPISODE_TOTAL,
         "intrusion episodes", "intrusion episodes", "sender"),
    
]

# probes for sender-studies
SITUATIONS = {"warning": "warning", 
              "infected_finding": "infected finding",
              "clean_finding": "clean finding", 
              "no_evidence": "no evidence"}


PROBE_POPULATIONS = {
    "warning": "observations with a warning for one or more of A's available servers",
    "infected_finding": "observations with an infected inspection finding for one or more of A's available servers",
    "clean_finding": "observations with a clean inspection finding for one or more of A's available servers",
    "no_evidence": "observations with at least one available server and no warning and no finding for any available server"}

PROBE_CONDITIONS = {
    "warning": "when it sees a warning for that server",
    "infected_finding": "when it sees an infected inspection finding for that server",
    "clean_finding": "when it sees a clean inspection finding for that server",
    "no_evidence": "when it sees no warning and no finding for any of its available servers"}


for _situation in SITUATIONS:
    
    BASE.append(_row(f"probe_interrupt_{_situation}",
                     f"probe_mean_probability_of_restore_or_isolate_given_{_situation}",
                     f"A's average probability of interrupting a server {PROBE_CONDITIONS[_situation]}", PROBE,
                     PROBE_POPULATIONS[_situation], "number of those observations", "sender"))


for _situation in SITUATIONS:
    
    BASE.append(_row(f"probe_greedy_interrupt_{_situation}",
                     f"probe_share_of_greedy_choices_that_are_restore_or_isolate_given_{_situation}",
                     f"share of A's greedy choices that interrupt a server {PROBE_CONDITIONS[_situation]}", PROBE,
                     PROBE_POPULATIONS[_situation], "number of those observations", "sender"))


# controls
CONTROL_BASES = ("reward", "b_infected_intervals", 
                 "b_infected_end", "b_unprompted_enabled", 
                 "b_unprompted_missed", "a_interrupts", 
                 "a_interrupt_relevant", "b_responds_to_a")

KIND = {}
for _base in BASE:
    KIND[_base["id"]] = _base["kind"]


def base_rows(sender: bool) -> list[dict]:

    rows = []
    
    for row in BASE:
        if sender or row["studies"] == "all":
            rows.append(row)
            
    return rows




def measurement_rows(sender: bool) -> list[dict]:


    bases = base_rows(sender)
    rows = list(bases)

    if sender:
        for base in bases:
            rows.append({"id": "before_" + base["id"], 
                         "long_name": "before_" + base["long_name"],
                         "plain_name": "the initial team's value of " + base["plain_name"], 
                         "kind": base["kind"],
                         "population": base["population"], 
                         "denominator": base["denominator"],
                         "base_id": base["id"], 
                         "studies": "sender"})


    for base in bases:
        if base["id"] not in CONTROL_BASES:
            continue
        
        denominator = base["denominator"]
        if base["kind"] == PER_INTERRUPTION:
            denominator = "none, a difference of two pooled rates, each over its own interruptions"
            
        rows.append({"id": "ctrl_" + base["id"], 
                     "long_name": "ctrl_" + base["long_name"],
                     "plain_name": "normal minus control, " + base["plain_name"], 
                     "kind": DIFFERENCE,
                     "population": base["population"], 
                     "denominator": denominator,
                     "base_id": base["id"], 
                     "studies": base["studies"]})

    return rows



def write_measurements_csv(path: str | Path, sender: bool) -> None:
    write_csv(path, measurement_rows(sender), MEASUREMENT_COLUMNS)
