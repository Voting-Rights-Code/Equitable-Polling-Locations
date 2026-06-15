'''Tests for python/solver/model_config.py config loading and validation.'''
import os

import yaml

from python.solver.model_config import PollingModelConfig

_REPO_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')
_BASE_DRIVING_YAML = os.path.join(
    _REPO_ROOT, 'datasets', 'configs', 'testing', 'testing_config_driving.yaml',
)


def _write_config(tmp_path, overrides=None, drop=()):
    '''Load the canonical driving config, apply overrides/drops, write to tmp, return path.'''
    with open(_BASE_DRIVING_YAML, 'r', encoding='utf-8') as base_file:
        data = yaml.safe_load(base_file)
    for key in drop:
        data.pop(key, None)
    if overrides:
        data.update(overrides)
    config_path = tmp_path / 'config.yaml'
    with open(config_path, 'w', encoding='utf-8') as out_file:
        yaml.safe_dump(data, out_file)
    return str(config_path)


def test_metric_loads_driving_distance(tmp_path):
    config_path = _write_config(tmp_path, overrides={'driving': True, 'metric': 'driving_distance'})
    config = PollingModelConfig.load_config(config_path)
    assert config.metric == 'driving_distance'


def test_metric_loads_haversine(tmp_path):
    config_path = _write_config(tmp_path, overrides={'driving': False, 'metric': 'haversine'})
    config = PollingModelConfig.load_config(config_path)
    assert config.metric == 'haversine'
