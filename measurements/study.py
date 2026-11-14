from measurements.glossary import KIND, PROBE, base_rows

RECEIVER_IDS = ("reward", 
                "b_infected_intervals",
                "b_infected_end", 
                "b_unprompted_enabled", 
                "b_unprompted_missed",
                "b_acts_on_peer_failure", 
                "clean_restores_b")

SENDER_IDS = ("reward",
              "b_infected_intervals",
              "b_infected_end", 
              "a_interrupt_relevant",
              "a_interrupt_relevant_b_closed",
              "a_interrupt_on_evidence_infected", 
              "a_interrupt_on_evidence_clean",
              "a_interrupts_clean", 
              "a_interrupt_b_unaware",
              "b_responds_to_a")


BASELINES = ("always-wait", "inspect-teacher", "restore-teacher")



def master_ids(sender: bool) -> list[str]:

    if not sender:
        return list(RECEIVER_IDS)

    ids = list(SENDER_IDS)
    
    for row in base_rows(True):
        if row["kind"] == PROBE:
            ids.append(row["id"])
            
    return ids



def _means(row: dict, column: str, summary_row: dict) -> None:
    row[f"{column}__mean"] = summary_row["mean"]
    row[f"{column}__sd"] = summary_row["sd"]
    row[f"{column}__teams"] = summary_row["teams"]


def _world_row(world_rows: list[dict], kind: str, arm: str, baseline: str) -> dict:

    found = []
    for row in world_rows:
        if row["row"] == kind and row["arm"] == arm and row["baseline"] == baseline:
            found.append(row)
            
            
    if len(found) != 1:
        raise ValueError(f"the world table has {len(found)} rows {kind} {arm} {baseline}, not one")

    return found[0]


def master_table(worlds: dict, sender: bool) -> list[dict]:
    
    ids = master_ids(sender)
    result = []

    for world, (arms, world_rows) in worlds.items():

        arm_names = list(arms)
        plain = {}
        controlled = []
        
        for arm, summary_rows in arms.items():
            
            plain[arm] = {}
            for summary_row in summary_rows:
                
                if summary_row["control"] == "":
                    plain[arm][summary_row["id"]] = summary_row
                    
                elif arm == arm_names[0]:
                    controlled.append(summary_row)


        row = {"world": world}
        difference = _world_row(world_rows, "arm difference", "", "")
        
        for id in ids:
            
            for arm in arm_names:
                _means(row, f"{id}__{arm}", plain[arm][id])
                
            row[f"{id}__arm_difference"] = difference[id]


        if not sender:
    
            for arm in arm_names:
                eligible = 0
                
                for world_row in world_rows:
                    
                    if world_row["row"] == "team" and world_row["arm"] == arm:
                        eligible += int(world_row["b_acts_on_peer_failure_denominator"])
                        
                row[f"b_acts_on_peer_failure__{arm}__eligible"] = eligible

        if sender:
            for id in ids:
                for arm in arm_names:
                    _means(row, f"before_{id}__{arm}", plain[arm][f"before_{id}"])
                    
            for arm in arm_names:
                row[f"a_interrupt_relevant__{arm}__teams_at_or_above_1_percent"] = (plain[arm]["a_interrupt_relevant"]["teams_at_or_above_1_percent"])

        a_waits = []
        for world_row in world_rows:
            if world_row["row"] == "baseline mean":
                a_waits.append(world_row)

        for id in ids:
            if KIND[id] == PROBE:
                continue
            for name in BASELINES:
                row[f"{id}__{name}"] = _world_row(world_rows, "baseline", "", name)[id]
            for world_row in a_waits:
                row[f"{id}__{world_row['baseline']}__{world_row['arm']}"] = world_row[id]

        for summary_row in controlled:
            _means(row, f"{summary_row['id']}__{summary_row['control']}", summary_row)

        result.append(row)


    columns = list(result[0])
    
    for row in result:
        
        if list(row) != columns:
            raise ValueError(f"the master table's row of {row['world']} has other columns than that of {result[0]['world']}")

    return result



SUMMARY_IDS = ("a_interrupt_relevant", "a_interrupt_on_evidence_infected", "b_responds_to_a", "reward")


def sender_studies_summary(masters: dict) -> list[dict]:

    result = []
    
    for study, (master_rows, arms) in masters.items():
        
        for master_row in master_rows:
            
            for arm in arms:
                
                row = {"study": study, "world": master_row["world"], "arm": arm}
                row["a_interrupt_relevant_mean"] = master_row[f"a_interrupt_relevant__{arm}__mean"]
                row["a_interrupt_relevant_teams"] = master_row[f"a_interrupt_relevant__{arm}__teams"]
                row["teams_at_or_above_1_percent"] = (master_row[f"a_interrupt_relevant__{arm}__teams_at_or_above_1_percent"])
                
                for id in SUMMARY_IDS[1:]:
                    row[f"{id}_mean"] = master_row[f"{id}__{arm}__mean"]
                    row[f"{id}_teams"] = master_row[f"{id}__{arm}__teams"]
                    
                result.append(row)

    return result


def sender_summary_columns() -> list[str]:
    
    
    columns = ["study",
               "world", 
               "arm",
               "a_interrupt_relevant_mean",
               "a_interrupt_relevant_teams",
               "teams_at_or_above_1_percent"]
    
    for id in SUMMARY_IDS[1:]:
        columns.extend([f"{id}_mean", f"{id}_teams"])
        
        
    return columns
