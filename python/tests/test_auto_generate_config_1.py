import pytest
import warnings
import yaml
import os
from model_config import (get_canonical_config_args, EXPERIMENTAL_FIELDS, CANONICAL_FIELDS)
# from auto_generate_config import generate_configs
tests_dir = 'tests'
testing_config_file = os.path.join(tests_dir, 'testing_auto_generate_config.yaml')

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