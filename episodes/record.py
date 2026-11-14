from dataclasses import asdict, dataclass

from actions.defender_action_encoding import build_defender_action_choices
from episodes.runner import EpisodeLog
from world.layout import build_server_partners
from world.state import create_initial_state


@dataclass
class EpisodeRecord:
    episode: int  # index within its evaluation or training block
    evaluation_seed: int | None  # None for a training episode
    iteration: int | None  # None for an evaluation episode
    script: dict  # intrusion {server, interval} or None, false_warnings, missed_servers, outages
    intervals: list[dict]
    boundaries: list[dict]  # each defender's observation facts
    initial_servers: dict  # every server's hidden truth at boundary 0
    total_reward: float

    @classmethod
    def from_log(cls, log: EpisodeLog, world: dict, episode: int,
                 evaluation_seed: int | None = None, iteration: int | None = None) -> "EpisodeRecord":

        choices = {}
        for defender in world["zones"]:
            choices[defender] = build_defender_action_choices(world, defender)

        intervals = []
        for t, report in enumerate(log.world_reports):

            defenders = {}
            for defender, defender_choices in choices.items():
                action_id = log.action_ids[t][defender]
                action, target = (None, None) if action_id is None else defender_choices[action_id]
                defenders[defender] = {"free": action_id is not None,
                                       "action": action,
                                       "target": target,
                                       "result": report["defender_command_results"].get(defender),
                                       "completed": report["defender_completions"].get(defender),
                                       "target_at_start": report["target_states_at_start"][defender]}

            requests = []
            for request in report["request_results"]:
                requests.append([request["source"], request["target"], request["succeeded"]])

            deliveries = {}
            for defender, warnings in report["monitoring_deliveries"].items():
                deliveries[defender] = {}
                for server, warning in warnings.items():
                    deliveries[defender][server] = warning["received_step"]

            reward = report["reward"]
            intervals.append({"defenders": defenders,
                              "reward": {"shared": reward["shared_reward"],
                                         "compromise_cost_by_zone": dict(reward["compromise_cost_by_zone"]),
                                         "compromised_server_count": reward["compromised_server_count"],
                                         "failed_request_count": reward["failed_request_count"],
                                         "inspection_start_count": reward["inspection_start_count"]},
                              "requests": requests,
                              "servers": report["servers"],
                              "intrusion": report["intrusion"],
                              "outages_started": list(report["outages_started"]),
                              "attacks_started": dict(report["attacks_started"]),
                              "attack_completions": dict(report["attack_completions"]),
                              "deliveries": deliveries})

        boundaries = []
        for facts in log.observation_facts:
            boundaries.append({"observations": facts})
        boundaries.append({"observations": log.final_observation_facts})

        initial_servers = {}
        for server, host in create_initial_state(world).hosts.items():
            if host.has_file_service:
                initial_servers[server] = {"compromised": host.compromised,
                                           "isolated": host.isolated,
                                           "service_running": host.file_service_running,
                                           "vulnerable": host.vulnerable}

        script = {"intrusion": log.script["intrusion"],
                  "false_warnings": list(log.script["false_warnings"]),
                  "missed_servers": list(log.script["missed_servers"]),
                  "outages": list(log.script["outages"])}

        return cls(episode=episode, evaluation_seed=evaluation_seed, iteration=iteration, script=script,
                   intervals=intervals, boundaries=boundaries, initial_servers=initial_servers,
                   total_reward=log.total_episode_reward)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "EpisodeRecord":
        return cls(**data)


def relevant_servers(record: EpisodeRecord, world: dict) -> dict[str, str] | None:
    
    intrusion = record.script["intrusion"]
    if intrusion is None:
        return None

    zone_of = {}
    for zone, values in world["zones"].items():
        for server in values["servers"]:
            zone_of[server] = zone

    server = intrusion["server"]
    partner = build_server_partners(world)[server]
    return {zone_of[server]: server, zone_of[partner]: partner}


def available(server_state: dict) -> bool:
    return bool(server_state["service_running"]) and not server_state["isolated"]


def action_labels(world: dict, defender: str) -> list[str]:

    labels = []
    
    for action, target in build_defender_action_choices(world, defender):
        labels.append(action if target is None else f"{action}_{target}")
        
    return labels
