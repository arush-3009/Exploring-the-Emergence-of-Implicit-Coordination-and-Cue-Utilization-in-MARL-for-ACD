import os

import pytest

from studies import launch
from studies.definitions import SMOKE

HANDPICKED = {
    "study-1-receiver-cue-utilization": """
[[timeline]]
evaluation_seed = 2001
episode = 3
folders = ["training-arms/cue-visible/teams/seed0-team", "training-arms/cue-hidden-unknown/teams/seed0-team"]
reason = "The same episode played by a team that sees its partner's failures and by one that does not."

[[timeline]]
evaluation_seed = 2002
episode = 7
folders = ["controls/cue-hidden-unknown-at-evaluation/seed1-team", "baselines/always-wait"]
reason = "A team with the cue removed at evaluation, beside the always-wait baseline."
""",
    "study-5-sender-inherited-a-fixed-b": """
[[timeline]]
evaluation_seed = 2001
episode = 0
folders = ["training-arms/cue-visible/teams/seed0-team",
           "controls/cue-hidden-failures-suppressed-at-evaluation/seed0-team",
           "training-arms/cue-visible/teams/seed0-team/before",
           "baselines/a-waits-with-fixed-b/cue-visible/seed0"]
reason = "A cue-visible team, the same episode with its failures suppressed, its initial team and A waiting."
"""}


def write_handpicked(folder):
    for study, text in HANDPICKED.items():
        path = folder / "runs/smoke/runs" / study / "worlds" / SMOKE["world"] / "handpicked.toml"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)


@pytest.fixture(scope="session")
def smoke_run(tmp_path_factory):
    folder = tmp_path_factory.mktemp("smoke")
    write_handpicked(folder)
    previous = os.getcwd()
    os.chdir(folder)
    try:
        launch.main(["--all", "--smoke", "--jobs", "2"])
    finally:
        os.chdir(previous)
    return folder
