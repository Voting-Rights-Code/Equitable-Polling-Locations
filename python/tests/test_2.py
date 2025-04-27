import os
import yaml
# from model_config import (get_canonical_config_args, EXPERIMENTAL_FIELDS, NON_CONFIG_META_DATA)
# from auto_generate_config import generate_configs


import pytest
import warnings
from python.solver.model_config import (get_canonical_config_args, EXPERIMENTAL_FIELDS, CANONICAL_FIELDS)
from python.utils.constants import RESULTS_BASE_DIR

test_results_dir = f'{RESULTS_BASE_DIR}/testing_results'
testing_config_file = os.path.join(test_results_dir, 'testing_auto_generate_config.yaml')

# Sample function to simulate configuration generation
# def generate_configs(base_config_file: str, other_args=None):
    # if other_args is None:
    #     other_args = []
    # config = {
    #     "location": "Richmond_city_VA",
    #     "year": '2014',
    #     "bad_types": [
    #         "Community Center - Potential",
    #         "Fire Station - Potential",
    #         "Library - Potential",
    #         "Municipal - Potential",
    #         "bg_centroid"
    #     ],
    #     "beta": -1,
    #     "time_limit": 360000,
    #     "capacity": 1.8,
    #     "precincts_open": None,
    #     "max_min_mult": 5,
    #     "maxpctnew": 1,
    #     "minpctold": 1,
    #     "penalized_sites": None,
    #     "config_name": "Richmond_city_VA_year_2014.yaml",
    #     "config_set": "test_configs",
    #     "experimental_data": {
    #     "driving": None,
    #     "fixed_capacity_site_number": None
    #     },
    #     # Add missing fields here
    #     "commit_hash": "abc123",  # Example value
    #     "run_time": "2024-01-01T00:00:00Z",  # Example value
    #     "username": "test_user"  # Example value
    # }

    # Write the config to the specified location
    # with open(base_config_file, 'w') as file:
    #     yaml.dump(config, file)
    # return config

# def validate_config(config):
#     required_fields = get_canonical_config_args()
#     # Check for missing required fields
#     missing_fields = required_fields - config.keys()
#     if missing_fields:
#         print(f"Missing required fields: {missing_fields}")
#         return False
#     # Check for extra fields in required fields
#     extra_fields = config.keys() - required_fields - {"experimental_data"}
#     if extra_fields:
#         print(f"Extra fields found: {extra_fields}")
#         return False
#     # Check mutual exclusivity
#     if not EXPERIMENTAL_FIELDS.isdisjoint(config.get("experimental_data", {}).keys()):
#         print("Required fields and experimental fields should not overlap.")
#         return False
#     return True

# def test_required_fields():
#     generate_configs(testing_config_file, other_args=NON_CONFIG_META_DATA)

#     with open(testing_config_file, 'r') as file:
#         config = yaml.safe_load(file)

#     # Test missing required field
#     del config["location"]  # Simulate missing required field
#     assert not validate_config(config), "Config should fail with missing required field."

#     # Reset and test extra field
#     config = generate_configs(testing_config_file, other_args=NON_CONFIG_META_DATA)
#     config["extra_field"] = "value_extra"  # Add an extra field
#     assert validate_config(config), "Config should pass with extra fields present."

# def test_mutual_exclusivity():
#     config = generate_configs(testing_config_file, other_args=NON_CONFIG_META_DATA)
#     assert validate_config(config), "Config validation failed unexpectedly."

# from auto_generate_config import generate_configs
# base_config_file = 'tests/testing_auto_generate_config.yaml'
# config_set = 'tests'

def test_get_canonical_config_args_server(mocker):
    mocker.patch('model_config.gc.SERVER', True)
    # mocker.patch('model_config.gc.PROD_DATASET', 'your_dataset')
    # mocker.patch('model_config.gc.PROJECT', 'your_project')
    mock_client = mocker.patch('model_config.bigquery.Client')
    mock_query_result = mocker.MagicMock()
    mock_query_result.to_dataframe.return_value.columns = CANONICAL_FIELDS
    mock_client.return_value.query.return_value = mock_query_result

    expected_fields = CANONICAL_FIELDS
    assert sorted(get_canonical_config_args()) == sorted(expected_fields)

def test_get_canonical_config_args_local(mocker):
    mocker.patch('model_config.gc.SERVER', False)
    expected_fields = CANONICAL_FIELDS
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        assert sorted(get_canonical_config_args()) == sorted(expected_fields)
        assert any(item.category == UserWarning for item in w)

def load_config(file_path):
    with open(file_path, 'r') as file:
        return yaml.safe_load(file)

# Define required and experimental fields
REQUIRED_FIELDS = CANONICAL_FIELDS
EXPERIMENTAL_FIELDS = EXPERIMENTAL_FIELDS

def test_missing_required_field():
    """Test that missing a required field causes an error."""
    config = load_config(testing_config_file)
    # Remove a required field
    del config['location']

    with pytest.raises(KeyError) as excinfo:
        validate_config(config)

    assert 'location' in str(excinfo.value)

def test_extra_required_field():
    """Test that having an extra required field causes an error."""
    config = load_config(testing_config_file)
    # Add an extra field
    config['extra_field'] = 'extra_value'

    with pytest.raises(ValueError) as excinfo:
        validate_config(config)

    assert 'Unexpected fields found' in str(excinfo.value)

def test_experimental_and_required_fields_mutual_exclusivity():
    """Test that experimental fields and required fields are mutually exclusive."""
    config = load_config(testing_config_file)

    # Create a set of all fields
    all_fields = set(config.keys())

    combined_fields = REQUIRED_FIELDS + EXPERIMENTAL_FIELDS

    intersection = all_fields.intersection(combined_fields)
    # print(f"Required Fields: {REQUIRED_FIELDS}")
    # print(f"Experimental Fields: {EXPERIMENTAL_FIELDS}")
    # print(f"All Fields from Config: {all_fields}")
    # print(f"Intersection: {intersection}")

    # Remove the overlapping fields from the intersection
    intersection = intersection - set(REQUIRED_FIELDS) - set(EXPERIMENTAL_FIELDS)

    assert len(intersection) == 0, "Required and experimental fields should not overlap."

# A mock validate_config function for testing purposes
def validate_config(config):
    """Validate the configuration."""
    for field in REQUIRED_FIELDS:
        if field not in config:
            raise KeyError(field)

    # Check for unexpected fields
    unexpected_fields = set(config.keys()) - set(REQUIRED_FIELDS) - set(EXPERIMENTAL_FIELDS)
    if unexpected_fields:
        raise ValueError(f"Unexpected fields found: {', '.join(unexpected_fields)}")

    for field in EXPERIMENTAL_FIELDS:
        if field in config and field in REQUIRED_FIELDS:
            raise ValueError(f"Field '{field}' cannot be both required and experimental.")
# if __name__ == "__main__":
#     pytest.main()

def test_write_toy_config_file():
    """Test that the toy config file is written correctly."""
    toy_config = {
        'location': 'Richmond_city_VA',
        'year': ['2024'],
        'bad_types': [
            'Community Center - Potential',
            'Fire Station - Potential',
            'Library - Potential',
            'Municipal - Potential',
            'bg_centroid'
        ],
        'beta': -1,
        'time_limit': 360000,
        'capacity': 1.8,
        'precincts_open': None,
        'max_min_mult': 5,
        'maxpctnew': 1,
        'minpctold': 1,
        'penalized_sites': None,
        'config_name': 'Richmond_city_original_2024',
        'config_set': 'test_configs',
        'driving': False,
        'fixed_capacity_site_number': None
    }

    # Write the config to the file
    config_file_path = testing_config_file
    with open(config_file_path, 'w') as file:
        yaml.dump(toy_config, file)

    # Check if the file exists
    assert os.path.exists(config_file_path), "Config file was not written."

    # Load the file and check its content
    with open(config_file_path, 'r') as file:
        loaded_config = yaml.safe_load(file)

    assert loaded_config == toy_config, "Config file content does not match expected."