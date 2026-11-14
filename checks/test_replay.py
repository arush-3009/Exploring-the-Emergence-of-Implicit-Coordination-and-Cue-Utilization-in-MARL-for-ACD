import json

import pytest
import torch

from episodes.record_io import read_records, read_run_json
from learning.networks import Actor, Critic
from studies.definitions import STUDIES
from studies.jobs import evaluate, save_weights
from studies.plan import greedy_actor, rule, world_settings
from studies.replay import play, replay_episode
from world.environment import WorldEnvironment

CODE = {"commit": "test", "changed_files": []}
WORLD = "one-false-warning-missed-warnings-outages"


def random_team(settings, path):
    environment = WorldEnvironment(settings)
    weights = {}
    for defender in environment.get_defender_ids():
        size = len(environment.encode_observation(defender))
        torch.manual_seed(len(weights))
        weights[defender] = {"actor": Actor(size, len(environment.action_choices(defender)), [16]).state_dict(),
                             "critic": Critic(size, [16]).state_dict()}
    save_weights(path, weights)


def stored(folder):
    records = {}
    for record in read_records(folder / "records.jsonl.gz"):
        records[(record.evaluation_seed, record.episode)] = json.loads(json.dumps(record.to_dict()))
    return records


@pytest.mark.parametrize("kind", ["rule", "actors"])
def test_a_replayed_episode_equals_the_record_the_evaluation_wrote(tmp_path, kind):
    settings = world_settings(STUDIES[2], WORLD, [])
    if kind == "rule":
        policies = {"A": rule("random"), "B": rule("inspect-teacher")}
    else:
        random_team(settings, tmp_path / "weights/final.pt")
        policies = {"A": greedy_actor(tmp_path / "weights/final.pt", [16]),
                    "B": greedy_actor(tmp_path / "weights/final.pt", [16])}
    evaluate(policies, settings, (2001, 2002), 4, tmp_path / "evaluation", {"kind": "test"}, CODE)

    run = read_run_json(tmp_path / "evaluation/run.json")
    assert run["settings"] == settings
    records = stored(tmp_path / "evaluation")
    assert len(records) == 8
    for evaluation_seed, episode in ((2001, 3), (2002, 0), (2002, 2)):
        _, replayed = replay_episode(run, evaluation_seed, episode)
        assert json.loads(json.dumps(replayed.to_dict())) == records[(evaluation_seed, episode)]

    assert records[(2001, 0)]["script"] != records[(2002, 0)]["script"] or \
        records[(2001, 1)]["script"] != records[(2002, 1)]["script"]

    with pytest.raises(ValueError, match="did not play"):
        replay_episode(run, 2003, 0)
    with pytest.raises(ValueError, match="did not play"):
        replay_episode(run, 2001, 4)


def test_a_changed_weights_file_is_refused(tmp_path):
    settings = world_settings(STUDIES[1], WORLD, [])
    random_team(settings, tmp_path / "final.pt")
    team = {"A": greedy_actor(tmp_path / "final.pt", [16]), "B": greedy_actor(tmp_path / "final.pt", [16])}
    evaluate(team, settings, (2001,), 1, tmp_path / "evaluation", {"kind": "test"}, CODE)
    run = read_run_json(tmp_path / "evaluation/run.json")

    weights = torch.load(tmp_path / "final.pt", weights_only=True)
    weights["A"]["actor"]["layers.0.bias"] += 1.0
    save_weights(tmp_path / "final.pt", weights)
    with pytest.raises(ValueError, match="not the weights file"):
        replay_episode(run, 2001, 0)


def test_an_observation_read_back_from_a_record_encodes_to_the_vector_the_actor_saw(tmp_path):
    settings = world_settings(STUDIES[3], WORLD, [{"observations.masks.suppress_peer_failures_when_local_available": ["B"]}])
    environment = WorldEnvironment(settings)
    checked = 0
    episodes = play({"A": rule("random"), "B": rule("random")}, settings, 2001)
    for _ in range(3):
        log, record = next(episodes)
        for boundary, observations in enumerate(log.observations):
            for defender in ("A", "B"):
                read_back = json.loads(json.dumps(record.boundaries[boundary]["observations"][defender], sort_keys=True))
                assert (environment.encode(defender, read_back) == observations[defender]).all()
                checked += 1
    assert checked == 3 * 50 * 2
