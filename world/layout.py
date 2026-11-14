from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


def build_server_partners(world_config: dict) -> dict[str, str]:
    partners = {}
    for first, second in world_config["network"]["server_pairs"]:
        partners[first] = second
        partners[second] = first
    return partners


@dataclass(frozen=True)
class WorldLayout:
    defender_ids: tuple[str, ...]
    servers: Mapping[str, tuple[str, ...]]
    employees: Mapping[str, str]
    partners: Mapping[str, str]
    server_slots: Mapping[str, Mapping[str, int]]

    @classmethod
    def from_config(cls, config: dict) -> "WorldLayout":
        zones = config["zones"]
        servers = {zone: tuple(values["servers"]) for zone, values in zones.items()}
        return cls(
            defender_ids=tuple(zones),
            servers=MappingProxyType(servers),
            employees=MappingProxyType({zone: values["employee"] for zone, values in zones.items()}),
            partners=MappingProxyType(build_server_partners(config)),
            server_slots=MappingProxyType({
                zone: MappingProxyType({host: i for i, host in enumerate(hosts, 1)})
                for zone, hosts in servers.items()
            }),
        )

    def __deepcopy__(self, memo):
        return self
