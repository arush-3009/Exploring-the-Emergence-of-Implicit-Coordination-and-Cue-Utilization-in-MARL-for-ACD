from measurements.glossary import KIND
from measurements.team import aggregate, by_episode

SERIES = ("a_restores",
          "a_isolates", 
          "a_interrupts", 
          "a_interrupt_relevant",
          "a_interrupt_on_evidence_infected", 
          "a_interrupt_on_evidence_clean", 
          "b_responds_to_a")


def training_columns() -> list[str]:
    columns = ["block", "first_iteration", "last_iteration", "episodes"]
    for id in SERIES:
        columns.extend([id, f"{id}_numerator", f"{id}_denominator"])
    return columns


def training_behaviour(episodes, block: int = 100) -> list[dict]:
    
    by_episode(episodes)
    
    blocks = {}
    
    for row in episodes:
        number = (int(row["iteration"]) - 1) // block
        if number not in blocks:
            blocks[number] = []
        blocks[number].append(row)

    result = []
    
    for number in sorted(blocks):
        rows = blocks[number]

       
        iterations = []
        for episode in rows:
            iterations.append(int(episode["iteration"]))

        row = {"block": number + 1, 
               "first_iteration": min(iterations),
               "last_iteration": max(iterations),
               "episodes": len(rows)}
        
        for id in SERIES:
            
            numerator, denominator = aggregate(KIND[id], id, rows)
            row[id] = numerator / denominator if denominator else None
            row[f"{id}_numerator"] = numerator
            row[f"{id}_denominator"] = denominator
            
        result.append(row)
        
    return result
