from random import Random

from world.state import Intrusion, WorldState


def randomly_draw_intrusion(settings: dict, generator: Random) -> Intrusion | None:

    clean = generator.random() < settings["clean_episode_share"]
    server = generator.choice(settings["servers"])
    first, last = settings["start_interval_range"]
    interval = generator.randint(first, last)

    return None if clean else Intrusion(server=server, interval=interval)


def apply_due_intrusion(state: WorldState) -> str | None:
    

    intrusion = state.intrusion
    if intrusion is None or intrusion.interval != state.elapsed_steps:
        return None

    host = state.hosts[intrusion.server]
    if not host.compromised:
        host.compromised = True
        state.compromise_started_steps[intrusion.server] = state.elapsed_steps

    return intrusion.server
