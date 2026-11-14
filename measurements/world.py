from measurements.arm import at_or_above_threshold, by_id, summary
from measurements.glossary import PROBE, base_rows, measurement_rows
from measurements.tables import optional_number


def plain_ids(sender: bool) -> list[str]:
    ids = []
    for row in measurement_rows(sender):
        if not row["id"].startswith("ctrl_"):
            ids.append(row["id"])
    return ids


def ctrl_ids(sender: bool) -> list[str]:
    ids = []
    for row in measurement_rows(sender):
        if row["id"].startswith("ctrl_"):
            ids.append(row["id"])
    return ids


def probe_ids(sender: bool) -> list[str]:
    ids = []
    for row in base_rows(sender):
        if row["kind"] == PROBE:
            ids.append(row["id"])
    return ids


def world_columns(controls: list[str], sender: bool) -> list[str]:

    columns = ["row", "arm", "seed", "baseline"]
    if sender:
        columns.append("below_1_percent")
    for id in plain_ids(sender):
        columns.extend([id, f"{id}_numerator", f"{id}_denominator"])
    for control in controls:
        for id in ctrl_ids(sender):
            columns.extend([f"{id}__{control}", f"{id}__{control}_numerator", f"{id}__{control}_denominator"])
        
        if sender:
            columns.extend([f"b_responds_to_a__{control}",
                            f"b_responds_to_a__{control}_numerator",
                            f"b_responds_to_a__{control}_denominator"])
    if sender:
        for id in probe_ids(sender):
            columns.append(f"{id}__arm_difference")

    return columns


def _empty_row(kind: str, arm: str, seed, baseline: str, controls: list[str], sender: bool) -> dict:

    row = {}
    for column in world_columns(controls, sender):
        row[column] = None
    row.update({"row": kind, "arm": arm, "seed": seed, "baseline": baseline})

    return row



def _copy(row: dict, rows: list[dict], ids: list[str], suffix: str, source: str) -> None:

    for id, measured in by_id(rows).items():
        
        if id not in ids:
            raise ValueError(f"{source} holds {id}, which the world table has no column for")
        
        column = id + suffix
        
        row[column] = measured["value"]
        row[f"{column}_numerator"] = measured["numerator"]
        row[f"{column}_denominator"] = measured["denominator"]


def world_table(arms: dict, teams: dict, baselines: list, controls: dict, sender: bool) -> list[dict]:


    arm_names = list(arms)
    controlled = arm_names[0]
    control_names = []
    
    for control, _ in controls:
        if control not in control_names:
            control_names.append(control)

    plain = plain_ids(sender)
    ctrl = ctrl_ids(sender)
    result = []

    for (arm, seed), rows in teams.items():
        
        row = _empty_row("team", arm, seed, "", control_names, sender)
        _copy(row, rows, plain, "", f"team {arm} seed {seed}")
        
        own = by_id(rows)
        
        if sender:
            above = at_or_above_threshold(optional_number(own["a_interrupt_relevant"]["value"]))
            row["below_1_percent"] = None if above is None else not above
            
        if arm == controlled:
            
            for control in control_names:
                
                ctrl_rows = []
                
                for measured in controls[(control, seed)]:
                    
                    if measured["id"].startswith("ctrl_"):
                        ctrl_rows.append(measured)
                        
                _copy(row, ctrl_rows, ctrl, f"__{control}", f"control {control} seed {seed}")

                if sender:
                    response = by_id(controls[(control, seed)])["b_responds_to_a"]
                    _copy(row, [response], ["b_responds_to_a"], f"__{control}", f"control {control} seed {seed}")
                
            if sender:
                other = by_id(teams[(arm_names[1], seed)])
                for id in probe_ids(sender):
                    first = optional_number(own[id]["value"])
                    second = optional_number(other[id]["value"])
                    row[f"{id}__arm_difference"] = None if first is None or second is None else first - second
                    
                    
        result.append(row)

    
    groups = {}
    
    for name, arm, seed, rows in baselines:
        
        row = _empty_row("baseline", arm, seed, name, control_names, sender)
        _copy(row, rows, plain, "", f"baseline {name} {arm} {seed}")
        result.append(row)
        if arm != "":
            if (name, arm) not in groups:
                groups[(name, arm)] = []
            groups[(name, arm)].append(by_id(rows))

    for (name, arm), sources in groups.items():
        
        row = _empty_row("baseline mean", arm, None, name, control_names, sender)
        
        for id in sources[0]:
            values = []
            for source in sources:
                values.append(optional_number(source[id]["value"]))
            row[id] = summary(values)["mean"]
            
        result.append(row)

    means = {}
    for arm, summary_rows in arms.items():
        row = _empty_row("arm mean", arm, None, "", control_names, sender)
        means[arm] = {}
        for summary_row in summary_rows:
            column = summary_row["id"] if summary_row["control"] == "" else f"{summary_row['id']}__{summary_row['control']}"
            if column not in row:
                raise ValueError(f"the arm summary of {arm} holds {column}, which the world table has no column for")
            row[column] = summary_row["mean"]
            means[arm][column] = optional_number(summary_row["mean"])
        result.append(row)

    row = _empty_row("arm difference", "", None, "", control_names, sender)
    for id in plain:
        first = means[arm_names[0]].get(id)
        second = means[arm_names[1]].get(id)
        row[id] = None if first is None or second is None else first - second
    result.append(row)

    return result
