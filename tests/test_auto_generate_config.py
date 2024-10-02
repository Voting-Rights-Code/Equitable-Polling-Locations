import pytest
import yaml
import os
from auto_generate_config import (MissingFieldError, load_base_config, validate_required_fields, 
                                  generate_yaml_content, generate_configs)

@pytest.fixture
def sample_config():
    return {
        'config_name': 'test_config',
        'config_set': 'test_configs',
        'location': 'TestCity',
        'year': '2024',
        'precincts_open': '20',
        'capacity': 1.5
    }

@pytest.fixture
def temp_config_file(tmp_path, sample_config):
    config_file = tmp_path / "test_config.yaml"
    with open(config_file, 'w') as f:
        yaml.dump(sample_config, f)
    return config_file

def test_load_base_config(temp_config_file):
    config = load_base_config(temp_config_file)
    assert config['config_name'] == 'test_config'
    assert config['location'] == 'TestCity'

def test_validate_required_fields(sample_config):
    validate_required_fields(sample_config, ['config_name', 'location'])
    with pytest.raises(MissingFieldError):
        validate_required_fields(sample_config, ['non_existent_field'])

def test_generate_yaml_content(sample_config):
    content = generate_yaml_content(sample_config)
    assert "config_name: test_config" in content
    assert "location: TestCity" in content

def test_generate_configs(tmp_path, sample_config):
    base_config_file = tmp_path / "base_config.yaml"
    with open(base_config_file, 'w') as f:
        yaml.dump(sample_config, f)

    os.makedirs(tmp_path / "test_configs", exist_ok=True)

    generate_configs(str(base_config_file), 'precincts_open', ['25', '30'])

    assert (tmp_path / "tests" / "TestCity_precincts_open_25.yaml").exists()
    # assert (tmp_path / "test_configs" / "TestCity_precincts_open_30.yaml").exists()

def test_generate_configs_invalid_field(tmp_path, sample_config):
    base_config_file = tmp_path / "base_config.yaml"
    with open(base_config_file, 'w') as f:
        yaml.dump(sample_config, f)

    os.makedirs(tmp_path / "test_configs", exist_ok=True)

    with pytest.raises(ValueError, match="invalid_field not a valid field"):
        generate_configs(str(base_config_file), 'invalid_field', ['value'])

def test_generate_configs_mismatched_directory(tmp_path, sample_config):
    base_config_file = tmp_path / "mismatched_dir" / "base_config.yaml"
    os.makedirs(tmp_path / "mismatched_dir", exist_ok=True)
    with open(base_config_file, 'w') as f:
        yaml.dump(sample_config, f)

    with pytest.raises(ValueError, match="Config directory .* should match config_set value"):
        generate_configs(str(base_config_file), 'precincts_open', ['25'])

def test_generate_configs_mismatched_filename(tmp_path, sample_config):
    base_config_file = tmp_path / "test_configs" / "mismatched_name.yaml"
    os.makedirs(tmp_path / "test_configs", exist_ok=True)
    with open(base_config_file, 'w') as f:
        yaml.dump(sample_config, f)

    with pytest.raises(ValueError, match="Config file name .* should match config_name value"):
        generate_configs(str(base_config_file), 'precincts_open', ['25'])

def test_generate_configs_file_already_exists(tmp_path, sample_config):
    base_config_file = tmp_path / "test_configs" / "test_config.yaml"
    os.makedirs(tmp_path / "test_configs", exist_ok=True)
    with open(base_config_file, 'w') as f:
        yaml.dump(sample_config, f)

    # Create a file that would conflict with the generated config
    conflicting_file = tmp_path / "test_configs" / "TestCity_precincts_open_25.yaml"
    conflicting_file.touch()

    with pytest.raises(ValueError, match=".*already exists"):
        generate_configs(str(base_config_file), 'precincts_open', ['25'])