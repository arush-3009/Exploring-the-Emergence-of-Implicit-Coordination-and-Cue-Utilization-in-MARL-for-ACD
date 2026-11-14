from pathlib import Path

from world.settings import apply_overrides, load_world_settings

TEST_WORLD = Path(__file__).resolve().parent / "test-world"
TEST_SETTINGS = Path(__file__).resolve().parent / "test-settings"

# No starting infection and a random intrusion into any server.
RANDOM_INTRUSION = {"world.initial.compromised_servers": [],
                    "world.intrusion": {"servers": ["A1", "A2", "A3", "B1", "B2", "B3"],
                                        "start_interval_range": [0, 30],
                                        "clean_episode_share": 0.2}}

# The test world with its zones and servers renamed X and Y.
OTHER_ZONE_NAMES = {"world.zones": {"X": {"employee": "EA", "servers": ["X1", "X2", "X3"]},
                                    "Y": {"employee": "EB", "servers": ["Y1", "Y2", "Y3"]}},
                    "world.network.server_pairs": [["X1", "Y1"], ["X2", "Y2"], ["X3", "Y3"]],
                    "world.servers.vulnerable_servers": ["X1", "X2", "X3", "Y1", "Y2", "Y3"],
                    "world.initial.compromised_servers": ["X1"],
                    "observations.monitoring.extra_detector_zones": ["X"]}


def world_settings(overrides: dict | None = None) -> dict:

    return apply_overrides(load_world_settings(TEST_WORLD), overrides or {})
