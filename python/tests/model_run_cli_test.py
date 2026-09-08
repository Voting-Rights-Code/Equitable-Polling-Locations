''' Tests for python.scripts.model_run_cli.load_configs. '''

from pathlib import Path

from python.scripts.model_run_cli import load_configs


def _write_config(config_dir: Path, filename: str, config_set: str, config_name: str) -> Path:
    ''' Write a known-good testing config to config_dir/filename with the given
    config_set and config_name, and return its path. '''
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / filename
    config_path.write_text(
        f'config_set: {config_set}\n'
        f'config_name: {config_name}\n'
        'location: testing\n'
        'census_year: 2020\n'
        'year:\n'
        "    - '2020'\n"
        'bad_types:\n'
        "    - 'bg_centroid'\n"
        'beta: -2\n'
        'time_limit: 360000\n'
        'limits_gap: 0.0\n'
        'capacity: 5\n'
        'fixed_capacity_site_number: null\n'
        'precincts_open: 3\n'
        'max_min_mult: 5\n'
        'maxpctnew: 1\n'
        'minpctold: .5\n',
        encoding='utf-8',
    )
    return config_path


def test_config_name_mismatch_is_invalid(tmp_path):
    ''' A config whose config_name differs from its filename stem is rejected. '''
    config_dir = tmp_path / 'testing'
    config_path = _write_config(config_dir, 'mismatch.yaml', 'testing', 'something_else')

    valid, unused_configs = load_configs([str(config_path)], str(tmp_path))

    assert valid is False


def test_config_name_case_only_difference_is_valid(tmp_path):
    ''' A config_name that matches the filename stem apart from case is accepted. '''
    config_dir = tmp_path / 'testing'
    config_path = _write_config(config_dir, 'Foo.yaml', 'testing', 'foo')

    valid, unused_configs = load_configs([str(config_path)], str(tmp_path))

    assert valid is True
