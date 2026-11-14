from checks.scenario_helpers import world_settings
from episodes.record import EpisodeRecord

WORLD = world_settings({"world.initial.compromised_servers": []})["world"]
STEPS = WORLD["episode"]["max_steps"]

ZONE_SERVERS = {}
EMPLOYEE = {}
for _zone, _values in WORLD["zones"].items():
    ZONE_SERVERS[_zone] = list(_values["servers"])
    EMPLOYEE[_zone] = _values["employee"]
SERVERS = ZONE_SERVERS["A"] + ZONE_SERVERS["B"]
PARTNER = {}
for _first, _second in WORLD["network"]["server_pairs"]:
    PARTNER[_first] = _second
    PARTNER[_second] = _first

FINDING_CODES = {"clean": 0, "infected": 1}


class Episode:

    def __init__(self, intrusion=None, missed=(), hide=(), suppress=(), false_warnings=(), outages=()):
        self.script = {"intrusion": None if intrusion is None else {"server": intrusion[0], "interval": intrusion[1]},
                       "false_warnings": [], "missed_servers": list(missed), "outages": []}
        for server, interval in false_warnings:
            self.script["false_warnings"].append({"server": server, "interval": interval})
        for server, interval, duration in outages:
            self.script["outages"].append({"server": server, "interval": interval, "duration": duration})
        self.hide = hide
        self.suppress = suppress
        self.availability = {}
        self.choices = {}
        self.busy = set()
        self.completions = {}
        self.spreads = {}
        self.warnings = set()
        self.findings = {}
        self.rewards = {}

    def set(self, server, first, last=None, **flags):

        for t in range(first, (STEPS - 1 if last is None else last) + 1):
            self.availability.setdefault((server, t), {}).update(flags)

    def act(self, defender, interval, action, target=None, result="accepted", busy=0, target_at_start=None):

        self.choices[(defender, interval)] = {"action": action, "target": target, "result": result,
                                              "target_at_start": target_at_start}
        for t in range(interval + 1, interval + 1 + busy):
            self.busy.add((defender, t))

    def complete(self, defender, interval, action):
        self.completions[(defender, interval)] = action

    def spread(self, source, interval):

        self.spreads.setdefault(interval, {})[source] = "succeeded"

    def warn(self, defender, server, first, last=None):

        for boundary in range(first, (STEPS if last is None else last) + 1):
            self.warnings.add((defender, server, boundary))

    def find(self, defender, server, value, first, last=None):

        for boundary in range(first, (STEPS if last is None else last) + 1):
            self.findings[(defender, server, boundary)] = FINDING_CODES[value]

    def reward(self, interval, value):
        self.rewards[interval] = value

    def record(self, episode=0, evaluation_seed=2001, iteration=None) -> EpisodeRecord:
        initial = {}
        for server in SERVERS:
            initial[server] = {"compromised": False, "isolated": False, "service_running": True, "vulnerable": True}

        intrusion = self.script["intrusion"]
        compromised = {}
        vulnerable = {}
        for server in SERVERS:
            compromised[server] = False
            vulnerable[server] = True
        job = {"A": None, "B": None}

        intervals = []
        previous = initial
        for t in range(STEPS):
            intruded = intrusion["server"] if intrusion is not None and intrusion["interval"] == t else None
            if intruded is not None:
                compromised[intruded] = True

            defenders = {}
            inspections = 0
            for defender in ("A", "B"):
                entry = {"free": True, "action": "wait", "target": None, "result": "accepted",
                         "completed": None, "target_at_start": None}
                if (defender, t) in self.busy:
                    entry.update(free=False, action=None, result=None)
                elif (defender, t) in self.choices:
                    choice = self.choices[(defender, t)]
                    entry.update(action=choice["action"], target=choice["target"], result=choice["result"])
                    if choice["result"] == "accepted" and choice["target"] is not None:
                        target = choice["target"]
                        entry["target_at_start"] = choice["target_at_start"] or {
                            "compromised": compromised[target], "isolated": previous[target]["isolated"],
                            "service_running": previous[target]["service_running"], "vulnerable": vulnerable[target]}
                        job[defender] = target
                        if choice["action"] == "inspect":
                            inspections += 1
                defenders[defender] = entry

            for defender in ("A", "B"):
                defenders[defender]["completed"] = self.completions.get((defender, t))
                if defenders[defender]["completed"] == "restore":
                    compromised[job[defender]] = False
                    vulnerable[job[defender]] = False

            attack_completions = dict(self.spreads.get(t, {}))
            for source in attack_completions:
                compromised[PARTNER[source]] = True

            servers = {}
            for server in SERVERS:
                flags = self.availability.get((server, t), {})
                servers[server] = {"compromised": compromised[server],
                                   "isolated": flags.get("isolated", False),
                                   "service_running": flags.get("service_running", True),
                                   "vulnerable": vulnerable[server]}

            requests = []
            for zone, zone_servers in ZONE_SERVERS.items():
                for server in zone_servers:
                    requests.append([EMPLOYEE[zone], server, _up(servers[server])])
            for first, second in WORLD["network"]["server_pairs"]:
                requests.append([first, second, _up(servers[first]) and _up(servers[second])])
                requests.append([second, first, _up(servers[first]) and _up(servers[second])])

            failed = 0
            for request in requests:
                if not request[2]:
                    failed += 1
            infected_b = 0
            for server in ZONE_SERVERS["B"]:
                if servers[server]["compromised"]:
                    infected_b += 1
            shared = self.rewards.get(t, -2.0 * infected_b - 1.0 * failed - 0.5 * inspections)

            intervals.append({"defenders": defenders,
                              "reward": {"shared": shared, "compromise_cost_by_zone": {"A": 0.0, "B": 2.0 * infected_b},
                                         "compromised_server_count": infected_b, "failed_request_count": failed,
                                         "inspection_start_count": inspections},
                              "requests": requests,
                              "servers": servers,
                              "intrusion": intruded,
                              "outages_started": [],
                              "attacks_started": {},
                              "attack_completions": attack_completions,
                              "deliveries": {"A": {}, "B": {}}})
            previous = servers

        boundaries = []
        for boundary in range(STEPS + 1):
            truth = initial if boundary == 0 else intervals[boundary - 1]["servers"]
            results = {}
            if boundary > 0:
                for source, target, succeeded in intervals[boundary - 1]["requests"]:
                    results[(source, target)] = int(succeeded)
            observations = {}
            for defender in ("A", "B"):
                local = {}
                for server in ZONE_SERVERS[defender]:
                    up = _up(truth[server])
                    peer = results.get((server, PARTNER[server]), -1)
                    if defender in self.hide:
                        peer = -1
                    elif defender in self.suppress and peer == 0 and up:
                        peer = 1
                    warned = (defender, server, boundary) in self.warnings
                    finding = self.findings.get((defender, server, boundary), -1)
                    local[server] = {"service_running": int(truth[server]["service_running"]),
                                     "isolated": int(truth[server]["isolated"]),
                                     "employee_request_result": results.get((EMPLOYEE[defender], server), -1),
                                     "peer_request_result": peer,
                                     "warning_received": int(warned),
                                     "warning_age": 0 if warned else -1,
                                     "inspection_finding": finding,
                                     "inspection_age": 0 if finding != -1 else -1}
                observations[defender] = {"elapsed_steps": boundary,
                                          "extra_detector_available": int(defender == "A"),
                                          "job_action": 0, "job_target": 0, "job_remaining_steps": 0,
                                          "last_command_feedback": 0, "servers": local}
            boundaries.append({"observations": observations})

        total = 0.0
        for interval in intervals:
            total += interval["reward"]["shared"]
        return EpisodeRecord(episode=episode, evaluation_seed=evaluation_seed, iteration=iteration,
                             script=self.script, intervals=intervals, boundaries=boundaries,
                             initial_servers=initial, total_reward=total)


def _up(server_state):
    return server_state["service_running"] and not server_state["isolated"]


def pick(rows, *columns):

    picked = []
    for row in rows:
        values = []
        for column in columns:
            values.append(row[column])
        picked.append(values[0] if len(columns) == 1 else tuple(values))
    return picked
