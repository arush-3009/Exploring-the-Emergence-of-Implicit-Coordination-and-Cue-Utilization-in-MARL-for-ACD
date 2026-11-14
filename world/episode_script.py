# An episode's script holds its intrusion, its false warnings, the servers whose infection
# gets no warning (the missed warnings), and its outages.

from random import Random

from attacker.intrusion import randomly_draw_intrusion
from world.state import EpisodeScript, FalseWarning, Intrusion, Outage, WorldState

EVENT_KINDS = ("missed-warnings", "false-warnings", "outages")


def episode_rngs(seed: int, episode: int) -> dict[str, Random]:

    generators = {}
    
    for kind in EVENT_KINDS:
        generators[kind] = Random(f"{seed}-{kind}-{episode}")
        
    return generators



def draw_episode_script(world_config: dict,
                        observation_config: dict,
                        world_rng: Random,
                        event_draws: dict[str, Random]) -> EpisodeScript:

    intrusion = None
    if "intrusion" in world_config:
        intrusion = randomly_draw_intrusion(world_config["intrusion"], world_rng)

    missed_servers: tuple[str, ...] = ()
    
    false_warnings: tuple[FalseWarning, ...] = ()
    
    if "warnings" in observation_config: #having unreliability in warnings with false negatives and false positives.
         
        settings = observation_config["warnings"]
        
        servers = []
        for zone in world_config["zones"].values():
            servers.extend(zone["servers"])
                
        draws = event_draws["missed-warnings"]
        missed = []
        for server in servers:
            if draws.random() < settings["miss_share"]:
                missed.append(server)
        missed_servers = tuple(missed)

        draws = event_draws["false-warnings"]
        first, last = settings["interval_range"]
        drawn = []
        for _ in range(settings["false_warnings_per_episode"]):
            server = draws.choice(servers)
            interval = draws.randint(first, last)
            drawn.append(FalseWarning(server=server, interval=interval))
        false_warnings = tuple(drawn)

    outages: tuple[Outage, ...] = ()
    if "outages" in world_config:
        settings = world_config["outages"]
        draws = event_draws["outages"]
        first, last = settings["interval_range"]
       
        drawn = []
        for _ in range(settings["per_episode"]):
            server = draws.choice(settings["servers"])
            interval = draws.randint(first, last)
            drawn.append(Outage(server=server, interval=interval, duration=settings["duration_steps"]))
        outages = tuple(drawn)

    return EpisodeScript(intrusion=intrusion, false_warnings=false_warnings,
                         missed_servers=missed_servers, outages=outages)


def episode_script_from_dict(data: dict) -> EpisodeScript:

    intrusion = None
    if data["intrusion"] is not None:
        intrusion = Intrusion(server=data["intrusion"]["server"], interval=data["intrusion"]["interval"])

    false_warnings = []
    for item in data["false_warnings"]:
        false_warnings.append(FalseWarning(server=item["server"], interval=item["interval"]))

    outages = []
    for item in data["outages"]:
        outages.append(Outage(server=item["server"], interval=item["interval"], duration=item["duration"]))

    return EpisodeScript(intrusion=intrusion,
                         false_warnings=tuple(false_warnings),
                         missed_servers=tuple(data["missed_servers"]),
                         outages=tuple(outages))


def outage_active(state: WorldState, server: str) -> bool:
    for outage in state.script.outages:
        if outage.server == server and outage.interval <= state.elapsed_steps < outage.interval + outage.duration:
            return True
    return False


def apply_due_outages(state: WorldState) -> list[str]:

    started = []
    
    for outage in state.script.outages:
        
        host = state.hosts[outage.server]
        
        if outage.interval <= state.elapsed_steps < outage.interval + outage.duration:
            host.file_service_running = False
            
            if state.elapsed_steps == outage.interval:
                started.append(outage.server)
                
        elif (state.elapsed_steps == outage.interval + outage.duration
              and not outage_active(state, outage.server)
              and not _restore_in_progress(state, outage.server)):
            host.file_service_running = True
            
    return started


def _restore_in_progress(state: WorldState, server: str) -> bool:

    for defender in state.defenders.values():
        job = defender.job
        if job is not None and job.action == "restore" and job.target == server:
            return True
    return False
