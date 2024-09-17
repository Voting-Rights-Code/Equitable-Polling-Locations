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

class InvalidFieldError(Exception):
    '''Custom exception for invalid fields in the config.'''
    def __init__(self, field_name):
        self.field_name = field_name
        super().__init__(f"Invalid field in config: {self.field_name}")

# Canonical and optional lists
CANONICAL_FIELDS = [
    'location', 'year', 'bad_types', 'beta', 'time_limit', 'capacity', 'precincts_open', 
    'max_min_mult', 'maxpctnew', 'minpctold', 'penalized_sites', 'config_name', 'config_set', 
    'result_folder', 'config_file_path', 'log_file_path'
]

OPTIONAL_FIELDS = ['fixed_capacity_site_number', 'driving']

def load_base_config(config_file):
    '''Load the base configuration from the provided YAML file.'''
    with open(config_file, 'r') as file: 
        return yaml.safe_load(file)

def validate_required_fields(config, required_fields):
    '''Validates that all required fields are present in the config.'''
    for field in required_fields:
        if field not in config:
            raise MissingFieldError(field)
        
def validate_config_fields(config):
    '''Validates that the fields in the config are either in the canonical list or the optional list.'''
    all_fields = CANONICAL_FIELDS + OPTIONAL_FIELDS
    for field in config:
        if field not in all_fields:
            raise InvalidFieldError(field)
        
def generate_configs(base_config_file, output_dir, locations=None, years=None, bad_types_values=None, beta_values=None,
                     time_limits=None, capacity_values=None, precincts_open_values=None, max_min_mult_values=None,
                     maxpctnew_values=None, minpctold_values=None, penalized_sites_values=None, config_name_values=None,
                     config_set_values=None, result_folder_values=None, config_file_path_values=None, log_file_path_values=None, parameter_variations=None):
    """
    Generate YAML configurations by varying specified parameters while keeping others constant.
    """
    # Load the base configuration from the file
    base_config = load_base_config(base_config_file)

    # List of required fields that must be present in the base config
    required_fields = CANONICAL_FIELDS

    # Validate the base config for required fields
    validate_required_fields(base_config, required_fields)
    # Validate the base config for invalid fields
    validate_config_fields(base_config)

    # Auto-generated fields: commit_hash, run_time, username, run_id
    commit_hash = str(uuid.uuid4())[:8]  # Simulated commit hash (first 8 characters)
    run_time = datetime.now().isoformat()  # Current timestamp
    username = getpass.getuser()  # User running the script
    run_id = str(uuid.uuid4())  # Unique run ID

    # Set default values if not provided
    if locations is None:
        locations = ['York_SC']
    if years is None:
        years = ['2020']
    if bad_types_values is None:
        bad_types_values = ['bg_centroid']
    if beta_values is None:
        beta_values = [-1]
    if time_limits is None:
        time_limits = [360000]
    if capacity_values is None:
        capacity_values = [1.5]
    if precincts_open_values is None:
        precincts_open_values = [14, 15]
    if max_min_mult_values is None:
        max_min_mult_values = [5]
    if maxpctnew_values is None:
        maxpctnew_values = [0, 1]
    if minpctold_values is None:
        minpctold_values = np.arange(0.8, 1.0, 0.1).tolist()

    # If parameter_variations is provided, override specific parameters
    parameter_variations = parameter_variations or {}
    locations = parameter_variations.get("location", locations)
    years = parameter_variations.get("year", years)
    bad_types_values = parameter_variations.get("bad_types", bad_types_values)
    beta_values = parameter_variations.get("beta", beta_values)
    time_limits = parameter_variations.get("time_limit", time_limits)
    capacity_values = parameter_variations.get("capacity", capacity_values)
    precincts_open_values = parameter_variations.get("precincts_open", precincts_open_values)
    max_min_mult_values = parameter_variations.get("max_min_mult", max_min_mult_values)
    maxpctnew_values = parameter_variations.get("maxpctnew", maxpctnew_values)
    minpctold_values = parameter_variations.get("minpctold", minpctold_values)
    penalized_sites_values = parameter_variations.get("penalized_sites", penalized_sites_values)
    config_name_values = parameter_variations.get("config_name", config_name_values)
    config_set_values = parameter_variations.get("config_set", config_set_values)
    result_folder_values = parameter_variations.get("result_folder", result_folder_values)
    config_file_path_values = parameter_variations.get("config_file_path", config_file_path_values)
    log_file_path_values = parameter_variations.get("log_file_path", log_file_path_values)

    # Generate combinations for the provided parameter variations
    for location in locations:
        for year in years:
            for bad_type in bad_types_values:
                for beta in beta_values:
                    for time_limit in time_limits:
                        for capacity in capacity_values:
                            for precincts_open in precincts_open_values:
                                for max_min_mult in max_min_mult_values:
                                    for maxpctnew in maxpctnew_values:
                                        for minpctold in minpctold_values:
                                            for penalized_sites in penalized_sites_values:
                                                for config_name in config_name_values:
                                                    for config_set in config_set_values:
                                                        for result_folder in result_folder_values:
                                                            for config_file_path in config_file_path_values:
                                                                for log_file_path in log_file_path_values:

                                                                    config = base_config.copy()
                                                                    config.update({
                                                                        'location': location,
                                                                        'year': year,
                                                                        'bad_types': bad_type,
                                                                        'beta': beta,
                                                                        'time_limit': time_limit,
                                                                        'capacity': capacity,
                                                                        'precincts_open': precincts_open,
                                                                        'max_min_mult': max_min_mult,
                                                                        'maxpctnew': maxpctnew,
                                                                        'minpctold': minpctold,
                                                                        'penalized_sites': penalized_sites,
                                                                        'config_name': config_name,
                                                                        'config_set': config_set,
                                                                        'result_folder': result_folder,
                                                                        'config_file_path': config_file_path,
                                                                        'log_file_path': log_file_path, 
                                                                        'driving': True,
                                                                        'commit_hash': None,
                                                                        'run_time': None,
                                                                        'username': None,
                                                                        'run_id': None
                                                                    })

                                                                    # # Define the output file name based on the location and precincts_open
                                                                    file_name = f"{config['location']}_config_{precincts_open}_polls.yaml"
                                                                    file_path = os.path.join(output_dir, file_name)

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
                                                                        f"penalized_sites: {config['penalized_sites']}\n"
                                                                        f"config_name: {config['config_name']}\n"
                                                                        f"config_set: {config['config_set']}\n"
                                                                        f"result_folder: {config['result_folder']}\n"
                                                                        f"config_file_path: {config['config_file_path']}\n"
                                                                        f"log_file_path: {config['log_file_path']}\n"
                                                                        f"fixed_capacity_site_number: {config.get['fixed_capacity_site_number']}\n"
                                                                        f"driving: {config['driving']}\n"
                                                                        "\n"
                                                                        "# Auto-generated fields\n"
                                                                        f"commit_hash: {config['commit_hash']}\n"
                                                                        f"run_time: {config['run_time']}\n"
                                                                        f"username: {config['username']}\n"
                                                                        f"run_id: {config['run_id']}\n"
                                                                    )

                                                                    # Write the configuration to a YAML file
                                                                    with open(file_path, 'w') as yaml_file:
                                                                        yaml.dump(config, yaml_file)

                                                                    with open(file_path, 'w') as yaml_file:
                                                                        yaml_file.write(yaml_content)
                                                                    
                                                                    print(f"Generated {file_name}")
