from measurements.episode import SCRIPT_COLUMNS
from measurements.glossary import CONTROL_BASES, KIND, PER_INTERRUPTION, base_rows
from measurements.tables import flag, number
from measurements.team import by_episode, of_seed, put_value


def control_ids(sender: bool) -> list[str]:

    in_study = set()
    
    for row in base_rows(sender):
        in_study.add(row["id"])
        
    ids = []
    for id in CONTROL_BASES:
        if id in in_study and KIND[id] != PER_INTERRUPTION:
            ids.append(id)
            
    return ids



def paired_columns(sender: bool) -> list[str]:
    
    columns = ["episode", "evaluation_seed"]
    
    for id in control_ids(sender):
        columns.extend([f"{id}_eligible", f"{id}_normal", f"{id}_control"])
        
    if sender:
        columns.extend(["b_responds_to_a_numerator_normal", 
                        "b_responds_to_a_denominator_normal",
                        "b_responds_to_a_numerator_control", 
                        "b_responds_to_a_denominator_control"])
        
    return columns



def control_measurements(normal_episodes, control_episodes, sender: bool) -> tuple[list[dict], list[dict]]:


    ids = control_ids(sender)
    normal = by_episode(normal_episodes)
    control = by_episode(control_episodes)
    
    if set(normal) != set(control):
        raise ValueError("the control evaluation does not hold the same episodes as the normal one")


    keys = sorted(normal, key=lambda key: (int(key[0]), int(key[2])))
    
    paired = []
    
    for key in keys:
        normal_row = normal[key]
        control_row = control[key]
        
        
        for column in SCRIPT_COLUMNS:
            if normal_row[column] != control_row[column]:
                raise ValueError(f"episode {key}: the scripts differ in {column}")


        row = {"episode": normal_row["episode"], "evaluation_seed": normal_row["evaluation_seed"]}
        for id in ids:
            
            if normal_row[f"{id}_eligible"] != control_row[f"{id}_eligible"]:
                raise ValueError(f"episode {key}: the two evaluations disagree about the eligibility for {id}")
            
            row[f"{id}_eligible"] = normal_row[f"{id}_eligible"]
            row[f"{id}_normal"] = normal_row[id]
            row[f"{id}_control"] = control_row[id]
            
        if sender:
            for side, source in (("normal", normal_row), ("control", control_row)):
                row[f"b_responds_to_a_numerator_{side}"] = source["b_responds_to_a_numerator"]
                row[f"b_responds_to_a_denominator_{side}"] = source["b_responds_to_a_denominator"]
                
        paired.append(row)

    seeds = []
    for key in keys:
        if key[0] not in seeds:
            seeds.append(key[0])

    ctrl = []
    for id in ids:
        row = {"id": "ctrl_" + id}
        put_value(row, "", *_difference(paired, id))
        for seed in seeds:
            put_value(row, f"_{seed}", *_difference(of_seed(paired, seed), id))
            
        ctrl.append(row)

    if sender:
        row = {"id": "ctrl_b_responds_to_a"}
        _rate_difference(row, "", paired)
        for seed in seeds:
            _rate_difference(row, f"_{seed}", of_seed(paired, seed))
            
        ctrl.append(row)

    return paired, ctrl

# sum of normal minus control over relevant episodes.
def _difference(paired, id: str) -> tuple[float, int]:
    
    numerator = 0.0
    denominator = 0
    
    for row in paired:
        if flag(row[f"{id}_eligible"]):
            
            numerator += number(row[f"{id}_normal"]) - number(row[f"{id}_control"])
            denominator += 1
              
    return numerator, denominator



def _rate_difference(row: dict, suffix: str, paired) -> None:

    counts = {}
    
    for side in ("normal", "control"):
        numerator = 0
        denominator = 0
        
        for paired_row in paired:
            numerator += int(paired_row[f"b_responds_to_a_numerator_{side}"])
            denominator += int(paired_row[f"b_responds_to_a_denominator_{side}"])
            
        counts[side] = (numerator, denominator)

    value = None
    
    if counts["normal"][1] and counts["control"][1]:
        value = counts["normal"][0] / counts["normal"][1] - counts["control"][0] / counts["control"][1]
        
    row[f"value{suffix}"] = value
    row[f"numerator{suffix}"] = None
    row[f"denominator{suffix}"] = None
