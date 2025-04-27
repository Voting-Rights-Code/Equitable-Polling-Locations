import os
import yaml

from python.utils.constants import RESULTS_BASE_DIR

test_results_dir = f'{RESULTS_BASE_DIR}/testing_results'
testing_config_file = os.path.join(test_results_dir, 'testing_auto_generate_config.yaml')

# Function to simulate your generate_configs function
def generate_configs(base_config_file, field_to_vary, desired_range):
    # Simulated function that would generate a configuration
    config = {
        "required_fields": {
            "field1": "value1",
            "field2": "value2",
        },
        "experimental_fields": {
            "experimental_field": "value_experimental"
        }
    }
    # Write the config to the specified location
    with open(base_config_file, 'w') as file:
        yaml.dump(config, file)
    return config

def test_required_fields():
    # Create a toy config file
    generate_configs(testing_config_file, "field_to_vary", [1, 2, 3])

    # Load the generated config for validation
    with open(testing_config_file, 'r') as file:
        config = yaml.safe_load(file)

    # Test missing field
    del config["required_fields"]["field1"]  # Simulate missing required field
    assert not validate_config(config), "Config should fail with missing required field."

    # Reset config and test extra field
    config = generate_configs(testing_config_file, "field_to_vary", [1, 2, 3])
    config["required_fields"]["extra_field"] = "value_extra"  # Add an extra field
    assert validate_config(config), "Config should pass with extra fields present."

def test_mutual_exclusivity():
    config = generate_configs(testing_config_file, "field_to_vary", [1, 2, 3])

    required_fields = set(config["required_fields"].keys())
    experimental_fields = set(config["experimental_fields"].keys())

    assert len(required_fields.intersection(experimental_fields)) == 0, \
        "Required fields and experimental fields should not overlap."

def validate_config(config):
    # Implement your validation logic here
    required_fields = config.get("required_fields", {})
    return all(field in required_fields for field in ["field1", "field2"])

# Example run (in practice, this should be in a testing framework)
if __name__ == "__main__":
    test_required_fields()
    test_mutual_exclusivity()
    print("All tests passed!")
