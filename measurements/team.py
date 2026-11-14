from measurements.glossary import COUNT_KINDS, EPISODE_KINDS, PROBE, base_rows
from measurements.tables import flag, number


def team_columns(seeds: list[str]) -> list[str]:
    
    columns = ["id", "value", "numerator", "denominator"]
    for seed in seeds:
        columns.extend([f"value_{seed}", f"numerator_{seed}", f"denominator_{seed}"])
        
    return columns



def by_episode(episodes) -> dict:

    result = {}
    
    for row in episodes:
        
        key = (row["evaluation_seed"], row["iteration"], row["episode"])
        if key in result:
            raise ValueError(f"episode {key} has two rows")
        
        result[key] = row
        
    return result

# A measurement's pooled numerator and denominator 
# over episodes.csv by adding across the episodes.
def aggregate(kind: str, id: str, episodes) -> tuple[float, int]:

    numerator = 0.0
    denominator = 0

    if kind in EPISODE_KINDS:
        
        for row in episodes:
            if flag(row[f"{id}_eligible"]):
                numerator += number(row[id])
                denominator += 1
    
    elif kind in COUNT_KINDS:
        
        for row in episodes:
            numerator += int(row[f"{id}_numerator"])
            denominator += int(row[f"{id}_denominator"])
            
    else:
        raise ValueError(f"{id} is of kind {kind}, which is not aggregated from episodes.csv")

    return numerator, denominator



def of_seed(rows, seed: str) -> list[dict]:
    
    result = []
    
    for row in rows:
        if row["evaluation_seed"] == seed:
            result.append(row)
            
    return result



def team_measurements(episodes, probe, sender: bool, before=None) -> list[dict]:

    by_episode(episodes)
    
    seeds = []
    for row in episodes:
        if row["evaluation_seed"] not in seeds:
            seeds.append(row["evaluation_seed"])
            
    seeds.sort(key=int)

    by_seed = {}
    for seed in seeds:
        by_seed[seed] = of_seed(episodes, seed)

    rows = []
    for entry in base_rows(sender):
        if entry["kind"] == PROBE:
            continue
        row = {"id": entry["id"]}
        put_value(row, "", *aggregate(entry["kind"], entry["id"], episodes))
        for seed in seeds:
            put_value(row, f"_{seed}", *aggregate(entry["kind"], entry["id"], by_seed[seed]))
        rows.append(row)

    if probe is not None:
        
        for probe_row in probe:
            
            row = dict(probe_row)
            
            for seed in seeds:
                row[f"value_{seed}"] = None
                row[f"numerator_{seed}"] = None
                row[f"denominator_{seed}"] = None
                
            rows.append(row)


    if before is not None:
        
        for before_row in before:
            
            row = dict(before_row)
            row["id"] = "before_" + before_row["id"]
            
            rows.append(row)


    return rows



def put_value(row: dict, suffix: str, numerator: float, denominator: int) -> None:

    row[f"value{suffix}"] = numerator / denominator if denominator else None
    row[f"numerator{suffix}"] = numerator
    row[f"denominator{suffix}"] = denominator

