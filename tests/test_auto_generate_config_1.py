import pytest
import yaml
import os
from auto_generate_config import (load_base_config, generate_yaml_content, generate_configs)

tests_dir = 'tests'
mock_base_config_file = os.path.join(tests_dir, 'testing_auto_generate_config.yaml')

def test_load_base_config(tmp_path):
    config_file = tmp_path / "config.yaml"
    config_file.write_text("""
    key1: value1
    key2: value2
    """)
    config = load_base_config(config_file)
    assert config == {'key1': 'value1', 'key2': 'value2'}

def test_generate_yaml_content():
    config = {
        'key1': 'value1',
        'key2': ['item1', 'item2'],
        'key3': 'value3'
    }
    generate_yaml_content(config)


@pytest.fixture
def load_config_template():
    config_file_path = os.path.join(os.path.dirname(__file__), 'testing_auto_generate_config.yaml')
    with open(config_file_path, 'r') as file:
        return yaml.safe_load(file)

@pytest.fixture
def mock_base_config_file(tmp_path, load_config_template):
    config = load_config_template
    config['config_set'] = str(tmp_path)
    config_file_path = tmp_path / "Richmond_city_original_2024.yaml"
    with open(config_file_path, 'w') as f:
        yaml.dump(config, f)
    return str(config_file_path)


def test_generate_configs_valid(mock_base_config_file):
    generate_configs(mock_base_config_file, 'year', ['2014', '2016', '2018', '2020'])
    for year in ['2014', '2016', '2018', '2020']:
        assert os.path.isfile(os.path.join(os.path.dirname(mock_base_config_file), f'Richmond_year_{year}.yaml'))

def test_generate_configs_missing_required_fields(mock_base_config_file):
    # Create a config file intentionally missing required fields
    config = {
        'config_set': str(mock_base_config_file),
        'config_name': 'Richmond_city_original_2024',
        'location': 'Richmond'
    }
    with open(mock_base_config_file, 'w') as f:
        yaml.dump(config, f)

    # Expecting ValueError for missing fields
    with pytest.raises(ValueError, match='missing required fields'):
        generate_configs(mock_base_config_file, 'year', ['2014'])

def test_generate_configs_extra_fields(mock_base_config_file):
    # Get the directory of the mock config file
    config_directory = os.path.dirname(mock_base_config_file)
    
    # Create a config file with required fields plus an extra field
    config = {
        'config_set': config_directory,  # Set to the directory instead of the full file path
        'config_name': 'Richmond_city_original_2024',
        'location': 'Richmond',
        'year': '2022',
        'max_min_mult': 1,
        'capacity': 100,
        'run_time': 60,
        'bad_types': [],
        'precincts_open': 10,
        'penalized_sites': [],
        'maxpctnew': 50,
        'commit_hash': 'abc123',
        'time_limit': 120,
        'beta': 0.5,
        'minpctold': 25,
        'extra_field': 'not_allowed'  # This should trigger an unknown fields error
    }

    with open(mock_base_config_file, 'w') as f:
        yaml.dump(config, f)

    # This should raise a ValueError about unknown fields
    with pytest.raises(ValueError, match='unknown fields provided'):
        generate_configs(mock_base_config_file, 'year', ['2014', '2016', '2018', '2020'])

def test_generate_configs_invalid_field_to_vary(mock_base_config_file):
    with pytest.raises(ValueError, match='not a valid field'):
        generate_configs(mock_base_config_file, 'invalid_field', ['value1', 'value2'])

def test_generate_configs_file_already_exists(mock_base_config_file):
    generate_configs(mock_base_config_file, 'year', ['2014'])
    with pytest.raises(ValueError, match='already exists'):
        generate_configs(mock_base_config_file, 'year', ['2014'])