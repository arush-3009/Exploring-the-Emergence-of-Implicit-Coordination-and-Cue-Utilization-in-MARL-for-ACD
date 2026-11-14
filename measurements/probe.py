import json

from episodes.record import EpisodeRecord
from measurements.facts import check_record, finding, shown_available, warning
from measurements.glossary import SITUATIONS
from measurements.tables import flag, number

SOURCE_COLUMNS = ["probe", "source", "evaluation_seed", "episode", "boundary", "occurrences"]


def probe_list_columns(world: dict) -> list[str]:
    
    columns = ["probe", "observation"]
    
    for server in world["zones"]["A"]["servers"]:
        columns.append(f"{server}_situation")
        
    columns.append("no_evidence")
    
    return columns


# A's servers' situation
def situation(observed: dict) -> str | None:

    if not shown_available(observed):
        return None
    
    if warning(observed):
        return "warning"
    
    category = finding(observed)
    
    if category == "infected":
        return "infected_finding"
    
    if category == "clean":
        return "clean_finding"
    
    return "none"




def build_probe_list(sources: list[tuple[str, list[EpisodeRecord]]], world: dict) -> tuple[list[dict], list[dict]]:

    servers = world["zones"]["A"]["servers"]
    numbers = {}
    list_rows = []
    source_rows = []

    for label, records in sources:
        
        for record in records:
            check_record(record, world)
            
            for boundary in range(len(record.intervals)):
                
                if not record.intervals[boundary]["defenders"]["A"]["free"]:
                    continue

                observation = record.boundaries[boundary]["observations"]["A"]
                key = json.dumps(observation, sort_keys=True)
                if key in numbers:
                    source_rows[numbers[key]]["occurrences"] += 1
                    continue

                numbers[key] = len(list_rows)
                row = {"probe": len(list_rows), "observation": key}
                eligible = []
                for server in servers:
                    value = situation(observation["servers"][server])
                    row[f"{server}_situation"] = value
                    if value is not None:
                        eligible.append(value)

                no_evidence = bool(eligible)
                
                for value in eligible:
                    if value != "none":
                        no_evidence = False
                        
                row["no_evidence"] = int(no_evidence)

                list_rows.append(row)
                
                
                source_rows.append({"probe": row["probe"], 
                                    "source": label,
                                    "evaluation_seed": record.evaluation_seed, 
                                    "episode": record.episode,
                                    "boundary": boundary, 
                                    "occurrences": 1})


    return list_rows, source_rows


def interrupt_mass(answer: dict, shown: list[str]) -> tuple[float, bool]:

    probability = 0.0
    greedy = False

    for server in shown:
        probability += number(answer[f"restore_{server}"]) + number(answer[f"isolate_{server}"])
        greedy = greedy or answer["greedy"] in (f"restore_{server}", f"isolate_{server}")

    return probability, greedy


def probe_measurements(list_rows: list[dict[str, str]], 
                       answer_rows: list[dict[str, str]], 
                       world: dict) -> list[dict]:
    

    servers = world["zones"]["A"]["servers"]

    answers = {}
    for answer in answer_rows:
        if answer["probe"] in answers:
            raise ValueError(f"probe {answer['probe']} has two answers")
        answers[answer["probe"]] = answer
        
        
    numbers = set()
    for row in list_rows:
        numbers.add(row["probe"])
    if numbers != set(answers) or len(numbers) != len(list_rows):
        raise ValueError("every probe of the list needs exactly one answer")

    sums = {}
    for name in SITUATIONS:
        sums[name] = {"probability": 0.0, "greedy": 0, "count": 0}


    for row in list_rows:
        
        answer = answers[row["probe"]]

        servers_by_situation = {}
        for name in SITUATIONS:
            servers_by_situation[name] = []

        for server in servers:
            value = row[f"{server}_situation"]
            if value == "":
                continue
            if value == "none":
                servers_by_situation["no_evidence"].append(server)
            else:
                servers_by_situation[value].append(server)

        for name in ("warning", "infected_finding", "clean_finding"):
            shown = servers_by_situation[name]
            if not shown:
                continue
            probability, greedy = interrupt_mass(answer, shown)
            sums[name]["probability"] += probability
            sums[name]["greedy"] += int(greedy)
            sums[name]["count"] += 1

        if flag(row["no_evidence"]):
            probability, greedy = interrupt_mass(answer, servers_by_situation["no_evidence"])
            sums["no_evidence"]["probability"] += probability
            sums["no_evidence"]["greedy"] += int(greedy)
            sums["no_evidence"]["count"] += 1

    rows = []
    for kind, total in (("probe_interrupt", "probability"), ("probe_greedy_interrupt", "greedy")):
        for name in SITUATIONS:
            count = sums[name]["count"]
            rows.append({"id": f"{kind}_{name}",
                         "value": sums[name][total] / count if count else None,
                         "numerator": sums[name][total],
                         "denominator": count})
    return rows
