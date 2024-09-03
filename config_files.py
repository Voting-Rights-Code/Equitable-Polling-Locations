import yaml
import os

# Base configuration
base_config = {
    "location": "Hampton_city_VA",
    "year": 2024,
    "bad_types": "'bg_centroid'",  # This should remain as a string or be adjusted according to the structure
    "beta": -1,
    "time_limit": 360000,  # 100 hours minutes
    "capacity": 1.5,
    # "precincts_open": 'null',
    "max_min_mult": 5,  # scalar >= 1
    "maxpctnew": 0,  # in interval [0,1]
    "minpctold": 1  # in interval [0,1]
}

# Lists of possible values for parameters
locations = ['York_SC']  # Add more locations as needed
years = list(range(2022, 2030, 2))  # Specify the years you want to generate
bad_types_values = ['bg_centroid']
beta_values = [-1]
capacity_values = [1.5]
precincts_open_values = list(range(25, 30))  # Specify the precincts_open values you want
max_min_mult_values = [5]  # Specify the max_min_mult values you want
maxpctnew_values = [0]  # in interval [0,1]
minpctold_values = [1]


# Directory to save YAML files
output_dir = './Greenville_SC_original_configs'
os.makedirs(output_dir, exist_ok=True)

# Create a dictionary to hold parameter variations
parameter_variations = {
    # "location": locations,
    # "year": years,
    # "max_min_mult": max_min_mult_values,
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
            # f"year: {config['year']}\n"
            # f"bad_types: {config['bad_types']}\n"
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
