import os
import yaml
from base_config_new import generate_configs

base_config_file = 'base_config.yaml'
output_dir = './Richmond_city_VA_potential_configs'

# Create the output directory if it doesn't exist
os.makedirs(output_dir, exist_ok=True)

# List of precincts_open values to vary
precincts_open_values = [15, 16, 17]  # Customize this list

# Function to load an existing YAML file
def load_yaml(file_path):
    if os.path.isfile(file_path):
        with open(file_path, 'r') as file:
            return yaml.safe_load(file)
    return None

# Other required parameters for generate_configs
locations = ['Richmond_city_VA']
years = [2020]
bad_types_values = ['bg_centroid']
beta_values = [-1]
time_limits = [360000]
capacity_values = [1.8]
max_min_mult_values = [5]
maxpctnew_values = [1]
minpctold_values = [0.8]
other_args_values = ['some_other_args']  # Modify as per your use case

# Loop through precincts_open values
for i in precincts_open_values:
    # Define the output file path for precincts_open only
    config_file_path = os.path.join(output_dir, f'precincts_open_{i}.yaml')
    
    # Check if the file already exists
    existing_config = load_yaml(config_file_path)
    
    # If the file exists and the precincts_open value matches, skip generation
    if existing_config and existing_config.get('precincts_open') == i:
        print(f"File {config_file_path} already exists with precincts_open={i}, skipping generation.")
    else:
        # Define the parameter variations
        parameter_variations = {
            "location": locations,
            "year": years,
            "bad_types": bad_types_values,
            "beta": beta_values,
            "time_limit": time_limits,
            "capacity": capacity_values,
            "precincts_open": [i],  # This will change for each loop
            "max_min_mult": max_min_mult_values,
            "maxpctnew": maxpctnew_values,
            "minpctold": minpctold_values,
            "other_args": other_args_values
        }

        # Generate the configuration with all required parameters
        generate_configs(
            base_config_file, output_dir,
            locations=locations, years=years,
            bad_types_values=bad_types_values, beta_values=beta_values,
            time_limits=time_limits, capacity_values=capacity_values,
            precincts_open_values=[i], max_min_mult_values=max_min_mult_values,
            maxpctnew_values=maxpctnew_values, minpctold_values=minpctold_values,
            other_args_values=other_args_values,
            parameter_variations=parameter_variations
        )
        print(f"Generated: {config_file_path}")
