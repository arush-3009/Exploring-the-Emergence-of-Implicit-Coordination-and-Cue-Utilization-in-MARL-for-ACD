import pytest

from episodes.record import EpisodeRecord, available
from episodes.runner import EpisodeRunner, evaluation_seeds
from learning.imitation import teacher_policies
from measurements.decisions import peer_failure_decisions
from measurements.episode import measure_episode
from measurements.interruptions import interruptions_of
from measurements.opportunities import opportunities_of
from policies.random_policy import RandomPolicy
from studies.definitions import MASKS, SENDER_WORLD
from world.environment import WorldEnvironment
from world.environment_interface import EnvironmentInterface
from world.settings import apply_overrides, load_world_settings

OUTAGE_WORLD = "worlds/one-false-warning-missed-warnings-outages"


def played(rule, masks=None, episodes=40, seed=2001):
    overrides = dict(SENDER_WORLD)
    overrides.update(masks or {})
    settings = apply_overrides(load_world_settings(OUTAGE_WORLD), overrides)
    environment = WorldEnvironment(settings)
    defender_seeds, world_seed = evaluation_seeds(seed, environment.get_defender_ids())
    environment.set_world_rng(world_seed)
    if rule == "random":
        policies = {}
        for defender in environment.get_defender_ids():
            policies[defender] = RandomPolicy(len(environment.action_choices(defender)), defender_seeds[defender])
    else:
        policies = teacher_policies(environment, rule)
    runner = EpisodeRunner(EnvironmentInterface(environment), policies)
    records = []
    for episode in range(episodes):
        records.append(EpisodeRecord.from_log(runner.run(), settings["world"], episode, evaluation_seed=seed))
    return settings["world"], records


@pytest.mark.parametrize("rule", ["random", "inspect-then-restore", "restore-on-warning"])
def test_the_readings_agree_with_the_record_s_own_facts(rule):
    world, records = played(rule)
    checked = {"interruptions": 0, "scored opportunities": 0}
    for record in records:
        row = measure_episode(record, world, sender=True)

        compromised = failed = inspections = 0
        for interval in record.intervals:
            compromised += interval["reward"]["compromised_server_count"]
            failed += interval["reward"]["failed_request_count"]
            inspections += interval["reward"]["inspection_start_count"]
        assert row["reward"] == pytest.approx(record.total_reward)
        assert row["failed_requests"] == failed
        assert row["inspections_a"] + row["inspections_b"] == inspections
        if row["b_infected_intervals_eligible"]:
            assert row["b_infected_intervals"] + row["a_infected_intervals"] == compromised

        for interruption in interruptions_of(record, world):
            t = interruption["interval"]
            interval = record.intervals[t]
            assert not available(interval["servers"][interruption["target"]])
            for source, target, succeeded in interval["requests"]:
                if (source, target) == (interruption["paired_b_server"], interruption["target"]):
                    assert interruption["b_shown_failure"] == int(not succeeded)
            assert interruption["observable"] == int(available(interval["servers"][interruption["paired_b_server"]]))
            checked["interruptions"] += 1

        for opportunity in opportunities_of(record, world):
            if opportunity["score"]:
                entry = record.intervals[opportunity["first_interruption_interval"]]["defenders"]["A"]
                assert entry["target"] == opportunity["server"]
                assert entry["target_at_start"]["compromised"] == (opportunity["status"] == "infected")
                checked["scored opportunities"] += 1
    assert min(checked.values()) > 0, checked


@pytest.mark.parametrize("mask", ["cue-hidden-unknown", "cue-hidden-failures-suppressed"])
def test_neither_mask_leaves_an_eligible_peer_failure_decision_while_the_visible_cue_does(mask):
    world, records = played("random", MASKS[mask], episodes=60)
    for record in records:
        assert peer_failure_decisions(record, world) == (0, 0)

    world, records = played("random", episodes=60)
    eligible = 0
    for record in records:
        eligible += peer_failure_decisions(record, world)[0]
    assert eligible > 0
