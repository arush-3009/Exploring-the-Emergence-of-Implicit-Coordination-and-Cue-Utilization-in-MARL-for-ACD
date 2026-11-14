import json

from checks.scenario_helpers import world_settings
from episodes.record import EpisodeRecord, available, relevant_servers
from episodes.runner import EpisodeRunner
from world.environment import WorldEnvironment
from world.environment_interface import EnvironmentInterface

# action IDs, 0 is Wait, then inspect, isolate, restore, reconnect per server
ISOLATE_1, RESTORE_2 = 2, 7


class AtIntervals:

    def __init__(self, choices, max_steps):
        self.choices = choices
        self.max_steps = max_steps

    def __call__(self, observation):
        return self.choices.get(round(float(observation[0]) * self.max_steps), 0)


def played(choices_a, choices_b, overrides=None):
    settings = world_settings({"world.intrusion": {"servers": ["A2"], "start_interval_range": [3, 3],
                                                    "clean_episode_share": 0},
                               "world.outages": {"per_episode": 1, "duration_steps": 2, "interval_range": [2, 2],
                                                 "servers": ["B2"]},
                               **(overrides or {})})
    environment = WorldEnvironment(settings)
    policies = {"A": AtIntervals(choices_a, 50), "B": AtIntervals(choices_b, 50)}
    log = EpisodeRunner(EnvironmentInterface(environment), policies).run()
    return environment, log, EpisodeRecord.from_log(log, settings["world"], episode=4, evaluation_seed=2001)


def test_the_record_survives_json_and_its_facts_are_the_vectors_the_policies_saw():
    environment, log, record = played({0: ISOLATE_1, 3: RESTORE_2}, {2: RESTORE_2})
    assert EpisodeRecord.from_dict(json.loads(json.dumps(record.to_dict()))) == record
    assert len(record.intervals) == 50 and len(record.boundaries) == 51
    assert record.episode == 4 and record.evaluation_seed == 2001 and record.iteration is None
    assert record.total_reward == log.total_episode_reward == sum(interval["reward"]["shared"] for interval in record.intervals)
    for t in range(50):
        for defender in ("A", "B"):
            facts = record.boundaries[t]["observations"][defender]
            assert (environment.encode(defender, facts) == log.observations[t][defender]).all()
    assert record.boundaries[50]["observations"] == log.final_observation_facts
    assert record.initial_servers["A1"] == {"compromised": True, "isolated": False, "service_running": True,
                                            "vulnerable": True}
    assert record.script["intrusion"] == {"server": "A2", "interval": 3}
    assert record.script["outages"] == [{"server": "B2", "interval": 2, "duration": 2}]


def test_target_state_is_read_before_the_start_and_after_the_interval_s_intrusion_and_outage():
    _, _, record = played({0: ISOLATE_1, 1: ISOLATE_1, 3: RESTORE_2}, {2: RESTORE_2})
    first = record.intervals[0]["defenders"]["A"]
    assert (first["action"], first["target"], first["result"], first["completed"]) == ("isolate", "A1", "accepted", "isolate")
    assert first["target_at_start"] == {"compromised": True, "isolated": False, "service_running": True, "vulnerable": True}
    assert record.intervals[0]["servers"]["A1"]["isolated"] is True
    again = record.intervals[1]["defenders"]["A"]
    assert again["result"] == "already_satisfied" and again["target_at_start"] is None
    restore = record.intervals[3]["defenders"]["A"]
    assert restore["target_at_start"] == {"compromised": True, "isolated": False, "service_running": True, "vulnerable": True}
    assert record.intervals[3]["intrusion"] == "A2"
    assert record.intervals[3]["servers"]["A2"]["isolated"] is True
    assert record.intervals[3]["servers"]["A2"]["service_running"] is False
    outage_restore = record.intervals[2]["defenders"]["B"]
    assert outage_restore["result"] == "accepted"
    assert outage_restore["target_at_start"]["service_running"] is False
    assert record.intervals[2]["outages_started"] == ["B2"]
    busy = record.intervals[4]["defenders"]["A"]
    assert busy == {"free": False, "action": None, "target": None, "result": None, "completed": None,
                    "target_at_start": None}
    waiting = record.intervals[6]["defenders"]["B"]
    assert waiting["free"] and waiting["action"] == "wait" and waiting["target_at_start"] is None


def test_attack_events_deliveries_and_requests_are_kept():
    _, log, record = played({}, {})
    for t, report in enumerate(log.world_reports):
        interval = record.intervals[t]
        assert interval["attacks_started"] == report["attacks_started"]
        assert interval["attack_completions"] == report["attack_completions"]
        assert len(interval["requests"]) == len(report["request_results"])
        for defender, warnings in report["monitoring_deliveries"].items():
            for server, warning in warnings.items():
                assert interval["deliveries"][defender][server] == warning["received_step"]
    assert record.intervals[0]["attacks_started"] == {"A1": "B1"}
    assert record.intervals[1]["attack_completions"] == {"A1": "succeeded"}


def test_relevant_servers_and_availability():
    _, _, record = played({}, {})
    world = world_settings()["world"]
    assert relevant_servers(record, world) == {"A": "A2", "B": "B2"}
    record.script["intrusion"] = {"server": "B3", "interval": 5}
    assert relevant_servers(record, world) == {"B": "B3", "A": "A3"}
    record.script["intrusion"] = None
    assert relevant_servers(record, world) is None
    assert available({"service_running": True, "isolated": False})
    assert not available({"service_running": 1, "isolated": 1})
    assert not available({"service_running": 0, "isolated": 0})
