import pytest

from checks.scenario_helpers import RANDOM_INTRUSION, world_settings
from checks.test_teachers import play
from world.environment import WorldEnvironment
from world.state import EpisodeScript, FalseWarning, Intrusion


@pytest.mark.parametrize("infected", [False, True])
@pytest.mark.parametrize("later_warning", [False, True])
def test_inspection_retires_earlier_warnings_only_at_completion(tmp_path, infected, later_warning):
    env = WorldEnvironment(world_settings({**RANDOM_INTRUSION, "actions.restore.patches_server": True}))
    warnings = [FalseWarning("A2", 0)]
    if later_warning:
        warnings.append(FalseWarning("A2", 2))
    env.state.script = EpisodeScript(intrusion=Intrusion("A2", 0) if infected else None,
                                    false_warnings=tuple(warnings))
    first = env.step({"A": ("wait", None), "B": ("wait", None)})
    assert first["monitoring_deliveries"]["A"]["A2"]["received_step"] == 1
    env.step({"A": ("inspect", "A2"), "B": ("wait", None)})
    assert env.observe("A")["servers"]["A2"]["warning_received"] == 1
    final = env.step({"B": ("wait", None)})
    observation = env.observe("A")["servers"]["A2"]
    assert observation["inspection_finding"] == int(infected)
    assert observation["inspection_age"] == 0
    assert observation["warning_received"] == int(later_warning)
    assert observation["warning_age"] == (0 if later_warning else -1)
    assert bool(final["monitoring_deliveries"]["A"]) == later_warning
    assert first["monitoring_deliveries"]["A"]["A2"]["received_step"] == 1


@pytest.mark.parametrize("rule,second,expected", [
    ("inspect-then-restore", 7, [(6, "inspect", "A2"), (8, "inspect", "A2")]),
    ("restore-on-warning", 9, [(6, "restore", "A2"), (10, "reconnect", "A2"),
                               (11, "restore", "A2"), (15, "reconnect", "A2")]),
])
def test_teacher_handles_warning_delivered_after_completion_in_same_interval(tmp_path, rule, second, expected):
    script = EpisodeScript(false_warnings=(FalseWarning("A2", 5), FalseWarning("A2", second)))
    (commands, _), = play(tmp_path, rule, [script])
    assert commands["A"] == expected
