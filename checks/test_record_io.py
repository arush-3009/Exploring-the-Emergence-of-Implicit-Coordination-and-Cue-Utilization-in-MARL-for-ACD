from checks.scenario_helpers import world_settings
from episodes.record import EpisodeRecord
from episodes.record_io import (
    read_records,
    read_run_json,
    sha256_of,
    write_records,
    write_run_json,
)
from episodes.runner import EpisodeRunner
from policies.random_policy import RandomPolicy
from world.environment import WorldEnvironment
from world.environment_interface import EnvironmentInterface


def three_records():
    settings = world_settings()
    environment = WorldEnvironment(settings)
    runner = EpisodeRunner(EnvironmentInterface(environment), {"A": RandomPolicy(13, 1), "B": RandomPolicy(13, 2)})
    records = []
    for episode in range(3):
        records.append(EpisodeRecord.from_log(runner.run(), settings["world"], episode, evaluation_seed=2002))
    return records


def test_records_are_read_back_in_order_and_equal_records_give_equal_bytes(tmp_path):
    records = three_records()
    write_records(tmp_path / "a" / "records.jsonl.gz", records)
    write_records(tmp_path / "b" / "records.jsonl.gz", iter(records))
    assert list(read_records(tmp_path / "a" / "records.jsonl.gz")) == records
    assert sha256_of(tmp_path / "a" / "records.jsonl.gz") == sha256_of(tmp_path / "b" / "records.jsonl.gz")
    leftovers = []
    for path in (tmp_path / "a").iterdir():
        leftovers.append(path.name)
    assert leftovers == ["records.jsonl.gz"]


def test_run_json_round_trip(tmp_path):
    data = {"run kind": "baseline", "seeds": [2001, 2002], "nested": {"value": 0.5}}
    write_run_json(tmp_path / "folder" / "run.json", data)
    assert read_run_json(tmp_path / "folder" / "run.json") == data
