from base_config_new import generate_configs

base_config_file = 'base_config.yaml'
output_dir = './Richmond_city_VA_potential_configs'

# Specify only precincts_open values to vary
precincts_open_values = [16, 17, 18, 19, 20]

# Call the function with only precincts_open variations
generate_configs(base_config_file, output_dir, precincts_open_values=precincts_open_values)


