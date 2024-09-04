'''1st --> we have to arrange the base_config.yaml as per requirement.
2nd --> check generate_configs, if you want to change the range of any particular parameter.
3rd --> You have to off the comment out that parameter of parameter_variation which you want to change.
4th --> You have to copy the relative path of that particular folder where you want to save it and paste it on output_dir.'''

import yaml
import os
import numpy as np

def load_base_config(config_file):
    with open(config_file, 'r') as file:
        return yaml.safe_load(file)

def generate_configs(base_config_file, output_dir, locations=None, years=None, bad_types_values=None, beta_values=None,
                     capacity_values=None, precincts_open_values=None, max_min_mult_values=None,
                     maxpctnew_values=None, minpctold_values=None):

    # Load the base configuration from the file
    base_config = load_base_config(base_config_file)

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
        precincts_open_values = list(range(16, 30))
    if max_min_mult_values is None:
        max_min_mult_values = [5]
    if maxpctnew_values is None:
        maxpctnew_values = [0,1]
    if minpctold_values is None:
        minpctold_values = np.arange(0, 1.1, 0.1).tolist()

    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Create a dictionary to hold parameter variations
    parameter_variations = {
        # "location": locations,
        # "year": years,
        # "bad_types": bad_types_values,
        # "beta": beta_values,
        # "capacity": capacity_values,
        "precincts_open": precincts_open_values,
        # "max_min_mult": max_min_mult_values,
        # "maxpctnew": maxpctnew_values,
        # "minpctold": minpctold_values 
    }

    # Generate configurations based on combinations of parameters
    for config_name, param_values in parameter_variations.items():
        for value in param_values:
            config = base_config.copy()
            config[config_name] = value
            
            # Define the output file name
            file_name = f"{config['location']}_config_original_{value}.yaml"
            file_path = os.path.join(output_dir, file_name)
            
            # Create YAML content with comments
            yaml_content = (
                "#Constants for the optimization function\n"
                f"location: {config['location']}\n"
                "year:\n"
                f"  - '{config['year']}'\n"
                "bad_types:\n"
                f"    - {config['bad_types']}\n"
                f"beta: {config['beta']}\n"
                f"time_limit: {config['time_limit']} #100 hours minutes\n"
                f"capacity: {config['capacity']}\n"
                f"\n"
                "####Optional#####\n"
                f"precincts_open: {config['precincts_open']}\n"
                f"max_min_mult: {config['max_min_mult']} #scalar >= 1\n"
                f"maxpctnew: {config['maxpctnew']} # in interval [0,1]\n"
                f"minpctold: {config['minpctold']} # in interval [0,1]\n"
            )
            
            # Write the YAML content to a file
            with open(file_path, 'w') as yaml_file:
                yaml.dump(config, yaml_file)
            
            with open(file_path, 'w') as yaml_file:
                yaml_file.write(yaml_content)
            
            print(f"Generated {file_name}")


# Example usage of the function
base_config_file = 'base_config.yaml'
output_dir = './Richmond_city_VA_potential_configs'

generate_configs(base_config_file, output_dir)
