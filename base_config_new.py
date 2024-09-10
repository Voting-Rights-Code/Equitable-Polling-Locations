import yaml
import os
import numpy as np
import uuid
import getpass
from datetime import datetime

class MissingFieldError(Exception):
    '''Custom exception for missing required fields.'''
    def __init__(self, field_name):
        self.field_name = field_name
        super().__init__(f"Missing required field: {self.field_name}")

def load_base_config(config_file):
    '''Load the base configuration from the provided YAML file.'''
    with open(config_file, 'r') as file:
        return yaml.safe_load(file)

def validate_required_fields(config, required_fields):
    '''Validates that all required fields are present in the config.'''
    for field in required_fields:
        if field not in config:
            raise MissingFieldError(field)

def generate_configs(base_config_file, output_dir, locations=None, years=None, bad_types_values=None, beta_values=None,
                     capacity_values=None, precincts_open_values=None, max_min_mult_values=None,
                     maxpctnew_values=None, minpctold_values=None, parameter_variations=None):

    # Load the base configuration from the file
    base_config = load_base_config(base_config_file)

    # List of required fields that must be present in the base config
    required_fields = ['location', 'year', 'bad_types', 'beta', 'capacity', 'time_limit', 'precincts_open', 
                       'max_min_mult', 'maxpctnew', 'minpctold']

    # Validate the base config for required fields
    validate_required_fields(base_config, required_fields)

    # Auto-generated fields: commit_hash, run_time, username, run_id
    commit_hash = str(uuid.uuid4())[:8]  # Simulated commit hash (first 8 characters)
    run_time = datetime.now().isoformat()  # Current timestamp
    username = getpass.getuser()  # User running the script
    run_id = str(uuid.uuid4())  # Unique run ID

    # Set default values if not provided
    if locations is None:
        locations = ['York_SC']
    if years is None:
        years = list(range(2014, 2024, 2))
    if bad_types_values is None:
        bad_types_values = ['bg_centroid']
    if beta_values is None:
        beta_values = [-1]
    if capacity_values is None:
        capacity_values = [1.5]
    if precincts_open_values is None:
        precincts_open_values = list(range(14, 30))
    if max_min_mult_values is None:
        max_min_mult_values = [5]
    if maxpctnew_values is None:
        maxpctnew_values = [0, 1]
    if minpctold_values is None:
        minpctold_values = np.arange(0, 1.1, 0.1).tolist()

    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # If parameter_variations is not provided, use default variations
    if parameter_variations is None:
        parameter_variations = {
            "location": locations,
            "year": years,
            "bad_types": bad_types_values,
            "beta": beta_values,
            "capacity": capacity_values,
            "precincts_open": precincts_open_values,
            "max_min_mult": max_min_mult_values,
            "maxpctnew": maxpctnew_values,
            "minpctold": minpctold_values
        }

    # Validate required fields in parameter_variations
    validate_required_fields(parameter_variations, required_fields)

    # Generate configurations based on combinations of parameters
    for config_name, param_values in parameter_variations.items():
        for value in param_values:
            config = base_config.copy()
            config[config_name] = value

            # Automatically add commit_hash, run_time, username, and run_id
            config['commit_hash'] = commit_hash
            config['run_time'] = run_time
            config['username'] = username
            config['run_id'] = run_id

            # Define the output file name
            file_name = f"{config['location']}_config_{value}.yaml"
            file_path = os.path.join(output_dir, file_name)

            # Create YAML content with comments
            yaml_content = (
                "# Constants for the optimization function\n"
                f"location: {config['location']}\n"
                "year:\n"
                f"  - '{config['year']}'\n"
                "bad_types:\n"
                f"    - {config['bad_types']}\n"
                f"beta: {config['beta']}\n"
                f"time_limit: {config['time_limit']} # in minutes\n"
                f"capacity: {config['capacity']}\n"
                "\n"
                "#### Optional #####\n"
                f"precincts_open: {config['precincts_open']}\n"
                f"max_min_mult: {config['max_min_mult']} # scalar >= 1\n"
                f"maxpctnew: {config['maxpctnew']} # in interval [0,1]\n"
                f"minpctold: {config['minpctold']} # in interval [0,1]\n"
                "\n"
                "# Auto-generated fields\n"
                f"commit_hash: {config['commit_hash']}\n"
                f"run_time: {config['run_time']}\n"
                f"username: {config['username']}\n"
                f"run_id: {config['run_id']}\n"
            )

            # Write the YAML content to a file
            with open(file_path, 'w') as yaml_file:
                yaml.dump(config, yaml_file)

            # Overwrite the file with the formatted YAML content
            with open(file_path, 'w') as yaml_file:
                yaml_file.write(yaml_content)

            print(f"Generated {file_name}")

# Example usage of the function with parameter_variations as an argument
base_config_file = 'base_config.yaml'
output_dir = './Richmond_city_VA_potential_configs'

# Custom parameter variations with all required fields
parameter_variations = {
    "location": ['Richmond_city_VA'],
    "year": [2014, 2016],
    "bad_types": ['bg_centroid'],
    "beta": [-1],
    "capacity": [1.8],
    "time_limit": [360000],
    "precincts_open": [16, 17, 18],
    "max_min_mult": [5],
    "maxpctnew": [1],
    "minpctold": [0.8]
}

generate_configs(base_config_file, output_dir, parameter_variations=parameter_variations)
