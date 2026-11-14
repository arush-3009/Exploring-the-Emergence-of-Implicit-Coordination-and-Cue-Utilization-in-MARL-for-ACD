from figures.study_figures import QUESTIONS as STUDY_QUESTIONS
from figures.style import BASELINES, is_share, number, plain_name
from figures.world_figures import QUESTIONS as WORLD_QUESTIONS
from figures.world_figures import mean_of, team_rows
from studies.paths import study_title

RECEIVER_COLUMNS = ("reward", 
                    "b_infected_intervals",
                    "b_infected_end", 
                    "b_unprompted_enabled",
                    "b_acts_on_peer_failure")


SENDER_COLUMNS = ("reward", "b_infected_intervals", "b_infected_end", "a_interrupt_relevant", "b_responds_to_a")


def shown(id: str, cell) -> str:
    value = number(cell)
    if value is None:
        return "undefined"
    if is_share(id):
        
        if 0 < value < 0.01:
            return f"{value * 100:.2f}%"
        
        return f"{value * 100:.1f}%"
    return f"{value:.4g}"


def table(header: list[str], rows: list[list[str]]) -> list[str]:
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    for row in rows:
        lines.append("| " + " | ".join(row) + " |")
    return lines


def figure_lines(names: list[str], questions: dict) -> list[str]:
    lines = []
    for name in names:
        question = questions[name]
        lines.extend([f"### {question}", 
                      "",
                      f"![{question}](figures/{name}.png)",
                      "",
                      (f"The points drawn are in [figures/{name}.csv](figures/{name}.csv), the vector version in [figures/{name}.svg](figures/{name}.svg)."),
                      ""])
    return lines


def world_readme(study: str, 
                 world: str, 
                 sender: bool,
                 world_table: list[dict],
                 summaries: dict, 
                 figures: list[str],
                 timelines: list[tuple[str, str]]) -> str:


    ids = SENDER_COLUMNS if sender else RECEIVER_COLUMNS
    arms = list(summaries)
    episodes = team_rows(world_table, arms[0])[0]["reward_denominator"]

    rows = []
    for arm in arms:
        for row in team_rows(world_table, arm):
            cells = [f"{arm}, seed {row['seed']}"]
            if sender and row["below_1_percent"] == "1":
                cells[0] += ", under 1 percent interruptions of the attacked pair's server"
            for id in ids:
                cells.append(shown(id, row[id]))
            rows.append(cells)
        cells = [f"**{arm}, mean**"]
        for id in ids:
            mean, teams = mean_of(summaries[arm], id)
            cells.append(f"**{shown(id, mean)}** ({teams} teams)")
        rows.append(cells)

    a_waits_by_seed = {}
    for row in world_table:
        if row["row"] != "baseline":
            continue
        cells = []
        for id in ids:
            cells.append(shown(id, row[id]))
        if row["arm"] == "":
            rows.append([BASELINES[row["baseline"]][0], *cells])
        else:
            if row["seed"] not in a_waits_by_seed:
                a_waits_by_seed[row["seed"]] = []
            a_waits_by_seed[row["seed"]].append((row["baseline"], row["arm"], cells))
    for seed, versions in a_waits_by_seed.items():
        same = True
        for _, _, cells in versions:
            if cells != versions[0][2]:
                same = False
        if same:
            rows.append([f"{BASELINES[versions[0][0]][0]}, seed {seed}", *versions[0][2]])
        else:
            for baseline, arm, cells in versions:
                rows.append([f"{BASELINES[baseline][0]}, {arm}, seed {seed}", *cells])

    header = [""]
    for id in ids:
        header.append(plain_name(id))

    lines = [f"# {world.replace('-', ' ')}",
             
             "",
             
             (f"One world of {study_title(study)}. Every team, baseline and control is scored on the same {episodes} episodes; the trained teams and the controls choose greedily and the rule baselines follow their rules. One team is one pair of defenders A and B trained for one seed. A mean is over the teams that have a value, with their number; a value with nothing to count is shown as undefined, never as zero."),
             
             "",
             
             "## Teams and baselines",
             
             ""]
    
    lines.extend(table(header, rows))
    
    lines.extend(["",
                  
                  ("Every measurement of every team, baseline and control, with its numerator and denominator, is in [world_table.csv](world_table.csv). Each arm's five teams with their mean, standard deviation, minimum and maximum are in `training-arms/<arm>/arm_summary.csv`. The study's measurements.csv defines every measurement."),
                  
                  "",
                  
                  "## Figures",
                  
                  ""])
    
    lines.extend(figure_lines(figures, WORLD_QUESTIONS))

    lines.extend(["## Example episodes", ""])
    if not timelines:
        lines.append("No episode has been chosen yet.")
    for page, reason in timelines:
        lines.append(f"- [{page}](timelines/{page}): {reason}")
    lines.append("")

    return "\n".join(lines)


def study_readme(study: str, sender: bool, master: list[dict], figures: list[str], worlds: list[str]) -> str:

    ids = SENDER_COLUMNS if sender else RECEIVER_COLUMNS
    arms = []
    for column in master[0]:
        if column.startswith("reward__") and column.endswith("__mean"):
            arms.append(column[len("reward__"):-len("__mean")])

    header = ["world", "arm"]
    for id in ids:
        header.append(plain_name(id))
    rows = []
    for row in master:
        for arm in arms:
            cells = [f"[{row['world'].replace('-', ' ')}](worlds/{row['world']}/README.md)", arm]
            for id in ids:
                cells.append(f"{shown(id, row[f'{id}__{arm}__mean'])} ({row[f'{id}__{arm}__teams']} teams)")
            rows.append(cells)

    lines = [f"# {study_title(study)}",
             
             "",
             
             ("The study's five worlds side by side. A value is the mean over the arm's teams that have a value, with their number in brackets. Each world's README lists its teams one by one."),
             
             "",
             
             "## The worlds",
             
             ""]
    
    
    lines.extend(table(header, rows))
    lines.extend(["",
                  ("Every mean of the study with its standard deviation and number of teams, the baselines and the control differences are in [master_table.csv](master_table.csv). [measurements.csv](measurements.csv) gives every measurement's id, name, population and denominator."),
                  
                  "",
                  
                  "## Figures",
                  
                  ""])
    
    lines.extend(figure_lines(figures, STUDY_QUESTIONS))
    lines.extend(["## Worlds", ""])
    
    for world in worlds:
        lines.append(f"- [{world.replace('-', ' ')}](worlds/{world}/README.md)")
    lines.append("")

    return "\n".join(lines)
