''' To change the year value of the yaml file.
# Change the base_config, output_dir, range of i and file_name.
# Also note that yaml_content may change according to the requirement of the code.'''


# import yaml
import os

# Base configuration without year
base_config = {
    #Constants for the optimization function
    "location": "York_SC",
    "bad_types": ["'bg_centroid'"],
    "beta": -1,
    "time_limit": 360000, #100 hours minutes
    "capacity": 1.5,

    ####Optional#####
    "precincts_open": "null",
    "max_min_mult": 5, #scalar >= 1
    "maxpctnew": 0,    #in interval [0,1]
    "minpctold": 1   #in interval [0,1]
}

# Directory to save YAML files
output_dir = './York_SC_original_configs'
os.makedirs(output_dir, exist_ok=True)

# Generate configurations with different year values
for i in range(2024, 2030, 2): # Increment by 2
    # Add the year to the base configuration
    config = base_config.copy()
    config["year"] = i

    # Define the output file name 
    file_name = f"York_config_original_{i}.yaml"
    file_path = os.path.join(output_dir, file_name)

    # Create YAML content with comments
    yaml_content = (
        "#Constants for the optimization function\n"
        f"location: {config['location']}\n"
        "year:\n"
        + "\n".join([f"    - {year}" for year in config['year']]) + "\n"
        "bad_types:\n"
        + "\n".join([f"    - {bad_type}" for bad_type in config['bad_types']]) + "\n"
        f"beta: {config['beta']}\n"
        f"time_limit: {config['time_limit']} #100 hours minutes\n"
        f"capacity: {config['capacity']}\n"
        f"\n"
        "####Optional#####\n"
        f"precincts_open: {config['precincts_open']}\n"
        f"max_min_mult: {config['max_min_mult']} #scalar >= 1\n"
        f"maxpctnew: {config['maxpctnew']} # in interval [0,1]\n"
        f"minpctold: {config['minpctold']} # in interval [0,1]\n"
        f"\n"
        f"\n"
    )

    # Write the config to a YAML file
    # with open(file_path, 'w') as yaml_file:
    #     yaml.dump(config, yaml_file)
    
    # Write the YAML content with comments to a file
    with open(file_path, 'w') as yaml_file:
        yaml_file.write(yaml_content)

    print(f"Generated {file_name}")