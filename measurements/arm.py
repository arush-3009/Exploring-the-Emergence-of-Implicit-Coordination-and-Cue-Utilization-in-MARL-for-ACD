import statistics

from measurements.tables import optional_number
from measurements.training_series import SERIES

#threshold for a_interrupt_relevant.
THRESHOLD = 0.01


def summary(values: list) -> dict:

    defined = []
    for value in values:
        if value is not None:
            defined.append(value)

    if not defined:
        return {"mean": None, "sd": None, "minimum": None, "maximum": None, "teams": 0}

    sd = None
    if len(defined) > 1:
        sd = statistics.stdev(defined)

    if sd is not None:
        sd = round(sd, 10)

    return {"mean": round(statistics.fmean(defined), 10), 
            "sd": sd, "minimum": min(defined), 
            "maximum": max(defined),
            "teams": len(defined)}



def at_or_above_threshold(value: float | None) -> bool | None:
    if value is None:
        return None
    return value >= THRESHOLD


def arm_columns(seeds: list[int], sender: bool) -> list[str]:

    columns = ["id", "control"]
    
    for seed in seeds:
        columns.append(f"seed{seed}")
        
    columns.extend(["mean", "sd", "minimum", "maximum", "teams"])
    
    if sender:
        columns.append("teams_at_or_above_1_percent")

    return columns



def ids_of(rows: list[dict]) -> list[str]:
    ids = []
    for row in rows:
        ids.append(row["id"])
        
    return ids


def by_id(rows: list[dict]) -> dict:
    result = {}
    
    for row in rows:
        result[row["id"]] = row
        
    return result


def _summary_row(id: str, control: str, seeds: list[int], rows_of: dict, sender: bool) -> dict:

    values = []
    row = {"id": id, "control": control}
    
    for seed in seeds:
        value = optional_number(rows_of[seed][id]["value"])
        row[f"seed{seed}"] = value
        values.append(value)
        
    row.update(summary(values))

    if sender:
        row["teams_at_or_above_1_percent"] = None
        if id == "a_interrupt_relevant" and control == "":
            
            count = 0
            
            for value in values:
                if at_or_above_threshold(value):
                    count += 1
                    
            row["teams_at_or_above_1_percent"] = count

    return row


def arm_summary(teams: dict, controls: dict, sender: bool) -> list[dict]:

    seeds = sorted(teams)
    ids = ids_of(teams[seeds[0]])
    
    rows_of = {}
    
    for seed in seeds:
        
        if ids_of(teams[seed]) != ids:
            raise ValueError(f"the team of seed {seed} holds other measurements than the team of seed {seeds[0]}")
        
        rows_of[seed] = by_id(teams[seed])


    result = []
    for id in ids:
        result.append(_summary_row(id, "", seeds, rows_of, sender))

    for control, control_teams in controls.items():
        
        if sorted(control_teams) != seeds:
            raise ValueError(f"the control {control} holds seeds {sorted(control_teams)}, the arm {seeds}")
        
        ctrl_ids = []
        
        for id in ids_of(control_teams[seeds[0]]):
            if id.startswith("ctrl_"):
                ctrl_ids.append(id)
                
        control_rows_of = {}
        
        for seed in seeds:
            
            control_rows_of[seed] = by_id(control_teams[seed])
            
            for id in ctrl_ids:
                
                if id not in control_rows_of[seed]:
                    raise ValueError(f"the control {control} of seed {seed} has no row {id}")
                
        for id in ctrl_ids:
            result.append(_summary_row(id, control, seeds, control_rows_of, sender))

    return result


def learning_curve_columns(seeds: list[int]) -> list[str]:
    columns = ["iteration"]
    for seed in seeds:
        columns.append(f"seed{seed}")
    columns.extend(["mean", "sd", "teams"])
    return columns


def arm_learning_curve(curves: dict) -> list[dict]:

    seeds = sorted(curves)
    iterations = []
    for row in curves[seeds[0]]:
        iterations.append(row["iteration"])
    for seed in seeds:
        seed_iterations = []
        for row in curves[seed]:
            seed_iterations.append(row["iteration"])
        if seed_iterations != iterations:
            raise ValueError(f"the team of seed {seed} has other training iterations than the team of seed {seeds[0]}")

    result = []
    for index, iteration in enumerate(iterations):
        row = {"iteration": int(iteration)}
        values = []
        for seed in seeds:
            value = optional_number(curves[seed][index]["mean_reward"])
            row[f"seed{seed}"] = value
            values.append(value)
        statistics_of = summary(values)
        row["mean"] = statistics_of["mean"]
        row["sd"] = statistics_of["sd"]
        row["teams"] = statistics_of["teams"]
        result.append(row)

    return result


def training_behaviour_columns() -> list[str]:
    columns = ["block", "first_iteration", "last_iteration"]
    for id in SERIES:
        columns.extend([f"{id}_mean", f"{id}_sd", f"{id}_teams"])
    return columns


def arm_training_behaviour(series: dict) -> list[dict]:

    seeds = sorted(series)
    blocks = []
    
    for row in series[seeds[0]]:
        blocks.append((row["block"], row["first_iteration"], row["last_iteration"]))
        
    for seed in seeds:
        
        seed_blocks = []
        
        for row in series[seed]:
            seed_blocks.append((row["block"], row["first_iteration"], row["last_iteration"]))
            
            
        if seed_blocks != blocks:
            raise ValueError(f"the team of seed {seed} has other training blocks than the team of seed {seeds[0]}")


    result = []
    for index, (block, first, last) in enumerate(blocks):
        
        row = {"block": int(block), "first_iteration": int(first), "last_iteration": int(last)}
        
        for id in SERIES:
            values = []
            
            for seed in seeds:
                values.append(optional_number(series[seed][index][id]))
                
            statistics_of = summary(values)
            row[f"{id}_mean"] = statistics_of["mean"]
            row[f"{id}_sd"] = statistics_of["sd"]
            row[f"{id}_teams"] = statistics_of["teams"]
            
        result.append(row)

    return result
