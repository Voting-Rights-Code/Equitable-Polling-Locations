'''In this code we have to change only that paramter_variation, base_config and the output_dir as required.'''

import yaml
import os

def generate_configs(base_config, output_dir, locations=None, years=None, bad_types_values=None, beta_values=None,
                     capacity_values=None, precincts_open_values=None, max_min_mult_values=None,
                     maxpctnew_values=None, minpctold_values=None):

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
        precincts_open_values = list(range(25, 30))
    if max_min_mult_values is None:
        max_min_mult_values = [5]
    if maxpctnew_values is None:
        maxpctnew_values = [0]
    if minpctold_values is None:
        minpctold_values = [1]

    # Create the output directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)

    # Create a dictionary to hold parameter variations
    parameter_variations = {
        # "location": locations,
        "year": years,
        # "max_min_mult": max_min_mult_values,
        # "bad_types": bad_types_values,
        # "beta": beta_values,
        # "capacity": capacity_values,
        # "precincts_open": precincts_open_values,
        # "max_min_mult": max_min_mult_values,
        # "maxpctnew": maxpctnew_values,
        # "minpctold": minpctold_values 
    }

    # Generate configurations based on combinations of parameters
    for config_name, param_values in parameter_variations.items():
        # Create a config for each value in the parameter list
        for value in param_values:
            config = base_config.copy()
            config[config_name] = value
            
            # Define the output file name
            file_name = f"Greenville_configs_original_{value}_polls.yaml"
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
base_config = {
    "location": "Greenville_SC",
    "year": 2020,
    "bad_types": "'bg_centroid'",
    "beta": -1,
    "time_limit": 360000,  # 100 hours minutes
    "capacity": 1.5,
    "precincts_open": 'null',
    "max_min_mult": 5,  # scalar >= 1
    "maxpctnew": 0,  # in interval [0,1]
    "minpctold": 1  # in interval [0,1]
}

output_dir = './Greenville_SC_original_configs'

generate_configs(base_config, output_dir)
