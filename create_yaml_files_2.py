import os
import yaml
from base_config_2 import generate_configs

# Path to the base config YAML file
base_config_file = 'base_config.yaml'

# Directory to save the YAML files
output_dir = './Richmond_city_VA_potential_configs'
os.makedirs(output_dir, exist_ok=True)

# List of parameter values to vary
precincts_open_values = [15, 16, 17, 18]

# Canonical and optional lists
CANONICAL_FIELDS = [
    'location', 'year', 'bad_types', 'beta', 'time_limit', 'capacity', 'precincts_open', 
    'max_min_mult', 'maxpctnew', 'minpctold', 'penalized_sites', 'config_name', 'config_set', 
    'result_folder', 'config_file_path', 'log_file_path'
]

OPTIONAL_FIELDS = ['fixed_capacity_site_number', 'driving']

# Function to load an existing YAML file
def load_yaml(file_path):
    if os.path.isfile(file_path):
        with open(file_path, 'r') as file:
            return yaml.safe_load(file)
    return None

# Function to validate that all required fields are present and no extra fields are present
def validate_config_fields(config):
    all_fields = CANONICAL_FIELDS + OPTIONAL_FIELDS
    for field in CANONICAL_FIELDS:
        if field not in config:
            raise ValueError(f"Missing required field: {field}")
    for field in config:
        if field not in all_fields:
            raise ValueError(f"Invalid field in config: {field}")

# Constant parameters for generating configs
locations = ['Richmond_city_VA']
years = ['2020']
bad_types_values = ['bg_centroid']
beta_values = [-1]
time_limits = [360000]
capacity_values = [1.8]
max_min_mult_values = [5]
maxpctnew_values = [1]
minpctold_values = [0.8]
penalized_sites_values = ['null']
config_name_values = ['null']
config_set_values = ['null']
result_folder_values = ['null']
config_file_path_values = ['null']
log_file_path_values = ['null']

# Loop through each precincts_open value to generate YAML files
for i in precincts_open_values:
    # Define the output file path based on precincts_open
    config_file_path = os.path.join(output_dir, f'precincts_open_{i}.yaml')
    
    # Load existing config if the file already exists
    existing_config = load_yaml(config_file_path)
    
    # Check if the file already exists and skip generation if it matches
    if existing_config:
        try:
            validate_config_fields(existing_config)
            if existing_config.get('precincts_open') == i:
                print(f"File {config_file_path} already exists with precincts_open={i}, skipping generation.")
                continue
        except ValueError as e:
            print(f"Error in existing config file {config_file_path}: {e}")
    
    # Define only precincts_open variations (other fields stay constant)
    parameter_variations = {
        "location": locations,
        "year": years,
        "bad_types": bad_types_values,
        "beta": beta_values,
        "time_limit": time_limits,
        "capacity": capacity_values,
        "precincts_open": [i],
        "max_min_mult": max_min_mult_values,
        "maxpctnew": maxpctnew_values,
        "minpctold": minpctold_values,
        "penalized_sites": penalized_sites_values,
        "config_name": config_name_values,
        "config_set": config_set_values,
        "result_folder": result_folder_values,
        "config_file_path": config_file_path_values,
        "log_file_path": log_file_path_values
    }

    # Generate only one configuration for each precincts_open value
    generate_configs(
        base_config_file, output_dir,
        locations=locations, years=years,
        bad_types_values=bad_types_values, 
        beta_values=beta_values,
        time_limits=time_limits, 
        capacity_values=capacity_values,
        precincts_open_values=[i],
        max_min_mult_values=max_min_mult_values,
        maxpctnew_values=maxpctnew_values, 
        minpctold_values=minpctold_values,
        penalized_sites_values=penalized_sites_values,
        config_name_values=config_name_values,
        config_set_values=config_set_values,
        result_folder_values=result_folder_values,
        config_file_path_values=config_file_path_values,
        log_file_path_values=log_file_path_values,
        parameter_variations=parameter_variations
    )
    
    print(f"Generated: {config_file_path}")