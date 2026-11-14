from copy import deepcopy

import pytest

from checks.scenario_helpers import world_settings
from observations.monitoring import update_monitoring
from world.environment import WorldEnvironment
from world.state import MonitoringWarning

WAIT = {"A": ("wait", None), "B": ("wait", None)}


def configured(tmp_path, *, basic=6, extra=2, zones=('A',), initial=None, horizon=50):
    overrides = {"observations.monitoring": {"basic_delay_steps": basic, "extra_information_delay_steps": extra,
                                             "extra_detector_zones": list(zones)},
                 "world.episode.max_steps": horizon}
    if initial is not None:
        overrides["world.initial.compromised_servers"] = list(initial)
    return WorldEnvironment(world_settings(overrides))


def deliveries(report):
    return {
        (zone, host): record['received_step']
        for zone, warnings in report['monitoring_deliveries'].items()
        for host, record in warnings.items()
    }


def test_baseline_full_timeline_separates_infection_and_warning_boundaries():
    env = WorldEnvironment(world_settings())
    assert env.state.compromise_started_steps == {'A1': 0}
    expected = {2: {('A', 'A1'): 2}, 6: {('A', 'A1'): 6}, 8: {('B', 'B1'): 8}}
    for boundary in range(1, 13):
        report = env.step(WAIT)
        assert deliveries(report) == expected.get(boundary, {})
        assert env.state.elapsed_steps == boundary
        assert env.state.compromise_started_steps == ({'A1': 0} if boundary == 1 else {'A1': 0, 'B1': 2})
    assert env.state.defenders['A'].monitoring_warnings == {'A1': MonitoringWarning(6)}
    assert env.state.defenders['B'].monitoring_warnings == {'B1': MonitoringWarning(8)}


def test_one_interval_delay_does_not_warn_about_a_new_infection_immediately(tmp_path):
    env = configured(tmp_path, basic=1, extra=1, zones=('A', 'B'))
    assert deliveries(env.step(WAIT)) == {('A', 'A1'): 1}
    assert deliveries(env.step(WAIT)) == {}
    assert env.state.compromise_started_steps['B1'] == 2
    assert deliveries(env.step(WAIT)) == {('B', 'B1'): 3}


@pytest.mark.parametrize('zones', [(), ('A',), ('B',), ('A', 'B')])
def test_extra_coverage_is_local_and_basic_monitoring_still_runs(tmp_path, zones):
    env = configured(tmp_path, basic=4, extra=2, zones=zones, initial=('A1', 'B1'))
    expected = {2: {(zone, zone + '1'): 2 for zone in zones},
                4: {('A', 'A1'): 4, ('B', 'B1'): 4}}
    for boundary in range(1, 9):
        assert deliveries(env.step(WAIT)) == expected.get(boundary, {})
    assert set(env.state.defenders['A'].monitoring_warnings) == {'A1'}
    assert set(env.state.defenders['B'].monitoring_warnings) == {'B1'}


@pytest.mark.parametrize('extra,expected', [
    (2, {2: {('A', 'A1'): 2}}),
    (5, {2: {('A', 'A1'): 2}, 5: {('A', 'A1'): 5}}),
])
def test_equal_delays_coalesce_and_a_later_extra_warning_replaces_the_earlier_one(tmp_path, extra, expected):
    env = configured(tmp_path, basic=2, extra=extra)
    env.state.hosts['B1'].isolated = True
    for boundary in range(1, 8):
        assert deliveries(env.step(WAIT)) == expected.get(boundary, {})
    assert env.state.defenders['A'].monitoring_warnings['A1'].received_step == extra


def test_cleanup_at_threshold_cancels_both_pending_warnings(tmp_path):
    env = configured(tmp_path, basic=4, extra=4)
    report = env.step({'A': ('restore', 'A1'), 'B': ('wait', None)})
    assert deliveries(report) == {}
    for _ in range(3):
        assert deliveries(env.step({'B': ('wait', None)})) == {}
    assert not env.state.hosts['A1'].compromised
    assert env.state.compromise_started_steps == {}
    assert env.state.defenders['A'].monitoring_warnings == {}
    for _ in range(3):
        assert deliveries(env.step(WAIT)) == {}


def test_busy_restore_does_not_disable_monitoring_before_cleanup():
    env = WorldEnvironment(world_settings())
    env.step({'A': ('restore', 'A1'), 'B': ('wait', None)})
    assert deliveries(env.step({'B': ('wait', None)})) == {('A', 'A1'): 2}
    assert env.state.defenders['A'].job.remaining_steps == 2
    assert env.state.hosts['A1'].isolated
    assert not env.state.hosts['A1'].file_service_running
    for _ in range(2):
        env.step({'B': ('wait', None)})
    assert not env.state.hosts['A1'].compromised
    assert env.state.compromise_started_steps == {}
    assert env.state.defenders['A'].monitoring_warnings == {}


def test_restore_reconnect_reinfection_restarts_delay_with_no_open_warning():
    env = WorldEnvironment(world_settings())
    env.step(WAIT)
    env.step(WAIT)  # S2, A receives, B1 infected
    env.step({'A': ('restore', 'A1'), 'B': ('wait', None)})
    for _ in range(3):
        last = env.step({'B': ('wait', None)})
    assert env.state.elapsed_steps == 6
    assert deliveries(last) == {}  # cleanup wins over the basic warning at 6
    assert env.state.compromise_started_steps == {'B1': 2}
    env.step({'A': ('reconnect', 'A1'), 'B': ('wait', None)})  # S7
    env.step(WAIT)  # S8, B starts the reverse attack and receives the basic warning
    assert deliveries(env.step(WAIT)) == {}  # S9, A1 newly reinfected
    assert env.state.compromise_started_steps['A1'] == 9
    assert env.state.defenders['A'].monitoring_warnings == {}
    assert deliveries(env.step(WAIT)) == {}  # S10, new infection age 1
    assert deliveries(env.step(WAIT)) == {('A', 'A1'): 11}
    for _ in range(3):
        assert deliveries(env.step(WAIT)) == {}
    assert deliveries(env.step(WAIT)) == {('A', 'A1'): 15}


def test_clean_episode_never_invents_warning_or_infection_timing(tmp_path):
    env = configured(tmp_path, initial=())
    for _ in range(50):
        assert deliveries(env.step(WAIT)) == {}
    assert env.state.compromise_started_steps == {}
    assert all(not d.monitoring_warnings for d in env.state.defenders.values())


def test_final_boundary_receives_warning_and_reset_creates_independent_timing(tmp_path):
    env = configured(tmp_path, basic=1, extra=1, horizon=1)
    result = env.step(WAIT)
    assert result['episode_finished']
    assert deliveries(result) == {('A', 'A1'): 1}
    previous = env.state
    snapshot = deepcopy(previous)
    with pytest.raises(RuntimeError):
        env.step(WAIT)
    assert env.state == snapshot
    env.reset()
    assert env.state.elapsed_steps == 0
    assert env.state.compromise_started_steps == {'A1': 0}
    assert all(not d.monitoring_warnings for d in env.state.defenders.values())
    env.state.compromise_started_steps.clear()
    assert previous == snapshot
    assert WorldEnvironment(world_settings()).state.compromise_started_steps == {'A1': 0}


def test_delay_beyond_horizon_never_flushes_pending_detection(tmp_path):
    env = configured(tmp_path, basic=51, extra=52)
    for _ in range(50):
        assert deliveries(env.step(WAIT)) == {}


def test_reports_do_not_alias_warnings_and_warning_age_is_not_infection_age():
    env = WorldEnvironment(world_settings())
    env.step(WAIT)
    result = env.step(WAIT)
    delivered = env.state.defenders['A'].monitoring_warnings['A1']
    assert env.state.elapsed_steps - delivered.received_step == 0
    result['monitoring_deliveries']['A']['A1']['received_step'] = 999
    result['monitoring_deliveries']['A'].clear()
    later = env.step(WAIT)
    assert delivered.received_step == 2
    assert env.state.elapsed_steps - delivered.received_step == 1
    assert deliveries(later) == {}
    assert env.state.elapsed_steps - env.state.compromise_started_steps['A1'] == 3


def test_f_runs_after_workload_before_clock_and_only_changes_monitoring(monkeypatch):
    env = WorldEnvironment(world_settings())
    env.step(WAIT)
    calls = []
    workload, monitoring = env.run_workload, env.update_monitoring

    def run_workload():
        calls.append('E')
        assert env.state.elapsed_steps == 1
        assert env.state.hosts['B1'].compromised
        assert env.state.defenders['A'].monitoring_warnings == {}
        return workload()

    def update():
        calls.append('F')
        before = deepcopy(env.state)
        result = monitoring()
        assert env.state.elapsed_steps == 1
        assert env.state.hosts == before.hosts
        assert env.state.attack_jobs == before.attack_jobs
        assert env.state.request_results == before.request_results
        assert result['A']['A1'].received_step == 2
        return result

    monkeypatch.setattr(env, 'run_workload', run_workload)
    monkeypatch.setattr(env, 'update_monitoring', update)
    env.step(WAIT)
    assert calls == ['E', 'F']
    assert env.state.elapsed_steps == 2


@pytest.mark.parametrize('host,started,error', [
    ('missing', 0, ValueError), ('EA', 0, ValueError), (4, 0, TypeError),
    ('A1', True, TypeError), ('A1', 1.5, TypeError), ('A1', '0', TypeError),
    ('A1', -1, ValueError), ('A1', 1, ValueError),
])
def test_malformed_monitoring_record_raises_before_monitoring_mutation(host, started, error):
    env = WorldEnvironment(world_settings())
    env.state.compromise_started_steps[host] = started
    before = deepcopy(env.state)
    with pytest.raises(error):
        update_monitoring(env.state, env._observation_config)
    assert env.state == before
