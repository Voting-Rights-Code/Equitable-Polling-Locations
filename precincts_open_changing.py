''' To change the precincts_open value of the yaml file.
# Change the base_config, output_dir, range of i and file_name.
# Also note that yaml_content may change according to the requirement of the code.'''

# import yaml
import os

# Base configuration without precincts_open
base_config = {
    #Constants for the optimization function
    "location": "Hampton_city_VA",
    "year": ["'2024'"],
    "bad_types": ["'bg_centroid'"],
    "beta": -1,
    "time_limit": 360000, #100 hours minutes
    "capacity": 1.8,

    ####Optional#####
    "max_min_mult": 5, #scalar >= 1
    "maxpctnew": 1,    #in interval [0,1]
    "minpctold": ".8"   #in interval [0,1]
}

# Directory to save YAML files
output_dir = './Hampton_city_VA_potential_configs'
os.makedirs(output_dir, exist_ok=True)

# Generate configurations with different precincts_open values
for i in range(15, 16):
    # Add the precincts_open to the base configuration
    config = base_config.copy()
    config["precincts_open"] = i

    # Define the output file name
    file_name = f"Hampton_city_config_{i}_polls.yaml"
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