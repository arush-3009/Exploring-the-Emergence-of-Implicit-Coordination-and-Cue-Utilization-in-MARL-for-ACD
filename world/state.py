from dataclasses import dataclass, field

from actions.contracts import CommandFeedback, TargetedAction


@dataclass
class HostState:

    zone: str
    has_file_service: bool
    file_service_running: bool
    vulnerable: bool
    compromised: bool = False
    isolated: bool = False

#A targeted action in progress.
@dataclass
class DefenderJob:

    action: TargetedAction
    target: str
    remaining_steps: int


@dataclass
class AttackJob:

    target: str
    remaining_steps: int


@dataclass(frozen=True)
class InspectionFinding:

    compromised: bool
    completed_step: int


@dataclass(frozen=True)
class MonitoringWarning:

    # Index of the state at the right boundary of the interval in which the
    # warning is received. Interval t ends at S_(t+1), so received_step = t + 1.
    received_step: int


@dataclass(frozen=True)
class Intrusion:

    server: str
    interval: int


@dataclass(frozen=True)
class FalseWarning:

    server: str
    interval: int


@dataclass(frozen=True)
class Outage:

    server: str
    interval: int
    duration: int


@dataclass(frozen=True)
class EpisodeScript:

    intrusion: Intrusion | None = None
    false_warnings: tuple[FalseWarning, ...] = ()
    # Servers whose infection, if they get one this episode, monitoring never notices.
    missed_servers: tuple[str, ...] = ()
    outages: tuple[Outage, ...] = ()


@dataclass(frozen=True)
class FileRequestResult:

    source: str
    target: str
    succeeded: bool


@dataclass
class DefenderState:

    job: DefenderJob | None = None
    inspection_findings: dict[str, InspectionFinding] = field(default_factory=dict)
    monitoring_warnings: dict[str, MonitoringWarning] = field(default_factory=dict)
    last_command_feedback: CommandFeedback = "none"


@dataclass
class WorldState:

    hosts: dict[str, HostState]
    defenders: dict[str, DefenderState]
    elapsed_steps: int = 0
    
    attack_jobs: dict[str, AttackJob] = field(default_factory=dict)
    request_results: list[FileRequestResult] = field(default_factory=list)
    
    compromise_started_steps: dict[str, int] = field(default_factory=dict)

    script: EpisodeScript = field(default_factory=EpisodeScript)

    @property
    def intrusion(self) -> Intrusion | None:
        return self.script.intrusion


def create_initial_state(config: dict, script: EpisodeScript | None = None) -> WorldState:
    
    vulnerable_servers = set(config["servers"]["vulnerable_servers"])
    initial = config["initial"]
    compromised_servers = set(initial["compromised_servers"])
    isolated_servers = set(initial["isolated_servers"])
    stopped_services = set(initial["servers_with_stopped_services"])

    hosts = {}
    defenders = {}

    for zone_id, zone_config in config["zones"].items():
        
        defenders[zone_id] = DefenderState()
        
        employee_id = zone_config["employee"]
        hosts[employee_id] = HostState(
            zone=zone_id,
            has_file_service=False,
            file_service_running=False,
            vulnerable=False,
        )

        for server_id in zone_config["servers"]:
            hosts[server_id] = HostState(
                zone=zone_id,
                has_file_service=True,
                file_service_running=server_id not in stopped_services,
                vulnerable=server_id in vulnerable_servers,
                compromised=server_id in compromised_servers,
                isolated=server_id in isolated_servers,
            )

    return WorldState(
        hosts=hosts,
        defenders=defenders,
        compromise_started_steps={
            host_id: 0 for host_id, host in hosts.items() if host.compromised
        },
        script=EpisodeScript() if script is None else script,
    )
