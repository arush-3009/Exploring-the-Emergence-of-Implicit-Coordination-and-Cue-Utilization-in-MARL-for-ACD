import pytest

from checks.scenario_helpers import TEST_SETTINGS
from learning.training_config import read_training_config, validate_training_config


@pytest.mark.parametrize("table,key,value", [
    ("advantages", "gamma", 1.5), ("advantages", "gae_lambda", -0.1),
    ("ppo", "clip_epsilon", 1.0), ("ppo", "actor_learning_rate", 0),
    ("ppo", "entropy_coefficient", -0.01),
    ("training", "iterations", 0), ("training", "episodes_per_iteration", 2.5),
])
def test_settings_outside_their_range_are_rejected(table, key, value):
    config = read_training_config(TEST_SETTINGS / "training_config.toml")
    config[table][key] = value
    with pytest.raises(ValueError, match=key):
        validate_training_config(config)


def test_an_entropy_coefficient_of_zero_is_allowed():
    config = read_training_config(TEST_SETTINGS / "training_config.toml")
    config["ppo"]["entropy_coefficient"] = 0
    validate_training_config(config)
