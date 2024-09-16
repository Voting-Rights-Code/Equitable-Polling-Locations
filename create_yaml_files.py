''' 1. Check which parameter you want to vary
'''

import os
import yaml
from base_config_new_1 import generate_configs

# Path to the base config YAML file
base_config_file = 'base_config.yaml'

# Directory to save the YAML files
output_dir = './Richmond_city_VA_potential_configs'
os.makedirs(output_dir, exist_ok=True)

# List of parameter values to vary
years = [2014, 2016, 2018]
# precincts_open_values = [15, 16, 17, 18]

# Function to load an existing YAML file
def load_yaml(file_path):
    if os.path.isfile(file_path):
        with open(file_path, 'r') as file:
            return yaml.safe_load(file)
    return None

# Constant parameters for generating configs
# Modify based on use case
locations = ['Richmond_city_VA']      
# years = ['2020']                    
bad_types_values = ['bg_centroid']    
beta_values = [-1]                    
time_limits = [360000]                
precincts_open_values = ['null']
capacity_values = [1.8]               
max_min_mult_values = [5]             
maxpctnew_values = [1]                
minpctold_values = [0.8]              
other_args_values = ['some_other_args']  

# Loop through each precincts_open value to generate YAML files
for i in years:
    # Define the output file path based on year
    config_file_path = os.path.join(output_dir, f'year_{i}.yaml')
    
    # Load existing config if the file already exists
    existing_config = load_yaml(config_file_path)
    
    # Check if the file already exists and skip generation if it matches
    if existing_config and existing_config.get('years') == i:
        print(f"File {config_file_path} already exists with years={i}, skipping generation.")
    else:
        # Define only precincts_open variations (other fields stay constant)
        parameter_variations = {
            "location": locations,
            "year": [i],
            "bad_types": bad_types_values,
            "beta": beta_values,
            "time_limit": time_limits,
            "capacity": capacity_values,
            "precincts_open": precincts_open_values,  # Only vary this field
            "max_min_mult": max_min_mult_values,
            "maxpctnew": maxpctnew_values,
            "minpctold": minpctold_values,
            "other_args": other_args_values
        }

        # Generate only one configuration for each precincts_open value
        generate_configs(
            base_config_file, output_dir,
            locations=locations, years=[i],
            bad_types_values=bad_types_values, beta_values=beta_values,
            time_limits=time_limits, capacity_values=capacity_values,
            precincts_open_values=precincts_open_values,  # Only pass current precincts_open
            max_min_mult_values=max_min_mult_values,
            maxpctnew_values=maxpctnew_values, minpctold_values=minpctold_values,
            other_args_values=other_args_values,
            parameter_variations=parameter_variations
        )
        print(f"Generated: {config_file_path}")
