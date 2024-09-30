import pytest
import os
import yaml
from auto_generate_config import load_base_config, validate_required_fields, generate_yaml_content, generate_configs

# Sample configuration for testing
BASE_CONFIG = {
    'location': 'Richmond_city_VA',
    'year': [2024],
    'bad_types': ['Community Center - Potential', 'Fire Station - Potential'],
    'beta': -1,
    'time_limit': 360000,
    'capacity': 1.8,
    'precincts_open': 14,
    'max_min_mult': 5,
    'maxpctnew': 1,
    'minpctold': 1,
    'config_name': 'Richmond_city_VA.yaml',
    'config_set': 'test_configs',
    'driving': False,
    'fixed_capacity_site_number': None
}

@pytest.fixture
def mock_config_file(tmp_path):
    """Create a temporary config file for testing."""
    config_file = tmp_path / "mock_config.yaml"
    with open(config_file, 'w') as file:
        yaml.dump(BASE_CONFIG, file)
    return config_file

def test_load_base_config(mock_config_file):
    config = load_base_config(mock_config_file)
    assert config == BASE_CONFIG

def test_validate_required_fields():
    required_fields = ['location', 'year', 'bad_types', 'beta', 'time_limit', 'capacity']
    
    # Should not raise an error
    validate_required_fields(BASE_CONFIG, required_fields)

    # Test missing field
    with pytest.raises(Exception):
        validate_required_fields({k: BASE_CONFIG[k] for k in required_fields if k != 'year'}, required_fields)

def test_generate_yaml_content():
    expected_yaml = (
        "# Constants for the optimization function #\n"
        "location: Richmond_city_VA\n"
        "year:\n"
        "  - 2024\n"
        "bad_types:\n"
        "  - Community Center - Potential\n"
        "  - Fire Station - Potential\n"
        "beta: -1\n"
        "time_limit: 360000\n"
        "capacity: 1.8\n"
        "precincts_open: 14\n"
        "max_min_mult: 5\n"
        "maxpctnew: 1\n"
        "minpctold: 1\n"
        "config_name: Richmond_city_VA.yaml\n"
        "config_set: test_configs\n"
        "\n####Experimental Data####\n"
        "driving: False\n"
        "fixed_capacity_site_number: null\n"
    )
    
    yaml_content = generate_yaml_content(BASE_CONFIG)
    assert yaml_content.strip() == expected_yaml.strip()

def test_generate_configs(mocker, tmp_path):
    # Mock get_canonical_config_args to return the expected fields
    mocker.patch('auto_generate_config.get_canonical_config_args', return_value=['location', 'year', 'bad_types', 'beta', 'time_limit', 'capacity', 'driving', 'fixed_capacity_site_number'])
    
    # Create a temporary config file
    config_file_path = tmp_path / "test_configs" / "Richmond_city_original_2024.yaml"
    config_file_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(config_file_path, 'w') as file:
        yaml.dump(BASE_CONFIG, file)
    
    # Call the generate_configs function
    generate_configs(str(config_file_path), 'year', ['2014', '2016', '2018', '2020'])

    # Check that the generated files exist and contain expected content
    for year in ['2014', '2016', '2018', '2020']:
        generated_file = tmp_path / "test_configs" / f"Richmond_city_VA_year_{year}.yaml"
        assert generated_file.exists()
        with open(generated_file, 'r') as file:
            generated_content = yaml.safe_load(file)
            assert generated_content['year'] == [year]
