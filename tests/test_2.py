# import os
# import yaml
# from model_config import (get_canonical_config_args, EXPERIMENTAL_FIELDS, NON_CONFIG_META_DATA)
# from auto_generate_config import generate_configs

# tests_dir = 'tests'
# testing_config_file = os.path.join(tests_dir, 'testing_auto_generate_config.yaml')

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

import pytest
import warnings
from model_config import get_canonical_config_args, CANONICAL_FIELDS

def test_get_canonical_config_args_server(mocker):
    mocker.patch('model_config.gc.SERVER', True)
    mocker.patch('model_config.gc.PROD_DATASET', 'your_dataset')
    mocker.patch('model_config.gc.PROJECT', 'your_project')
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

# if __name__ == "__main__":
#     pytest.main()
