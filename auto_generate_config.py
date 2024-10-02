import yaml
import os
from model_config import (get_canonical_config_args, EXPERIMENTAL_FIELDS)


class MissingFieldError(Exception):
    '''Custom exception for missing required fields.'''
    def __init__(self, field_name):
        self.field_name = field_name
        super().__init__(f"Missing required field: {self.field_name}")

def load_base_config(config_file):
    '''Load the base configuration from the provided YAML file.'''
    with open(config_file, 'r') as file: 
        return yaml.safe_load(file)

def validate_required_fields(config, required_fields):
    '''Validates that all required fields are present in the config.'''
    for field in required_fields:
        if field not in config:
            raise MissingFieldError(field)
        
def generate_yaml_content(config):
    '''Generate YAML content dynamically based on the config.'''
    yaml_content = "# Constants for the optimization function #\n"
    
    for key in config.keys():
        value = config.get(key)
        if isinstance(value, list):
            yaml_content += f"{key}:\n"
            for item in value:
                yaml_content += f"  - {item}\n"
        else:
            yaml_content += f"{key}: {value}\n"

    yaml_content += "\n####Experimental Data####\n"
    for field in EXPERIMENTAL_FIELDS:
        yaml_content += f"{field}: {config.get(field, 'null')}\n"

    return yaml_content

def generate_configs(base_config_file:str, field_to_vary:str, desired_range: list, other_args = EXPERIMENTAL_FIELDS):
    """
    Generate YAML configurations by varying specified parameters while keeping others constant.
    """
    # Load the base configuration from the file
    base_config = load_base_config(base_config_file)
    
    # List of required fields that must be present in the base config
    required_fields = get_canonical_config_args(True)
    all_fields = required_fields + other_args
    
    # Validate the base config for correct fields
    config_fields = base_config.keys()
    missing_fields = set(required_fields).difference(set(config_fields))
    extra_fields = set(config_fields).difference(all_fields)
    # breakpoint()
    if len(missing_fields) >0:
        raise ValueError(f'missing required fields: {missing_fields}')
    if len(extra_fields) >0:
        raise ValueError(f'unknown fields provided: {extra_fields}')
    
    #validate config name and set
    config_set = base_config['config_set']
    config_dir = os.path.dirname(base_config_file)
    config_file_name = os.path.splitext(os.path.basename(base_config_file))[0]
    config_name = base_config['config_name']
    if (config_dir != config_set):
        raise ValueError(f'Config directory ({config_dir}) should match config_set value ({config_set})')
    if (config_file_name != config_name):
        raise ValueError(f'Config file name ({config_file_name}) should match config_name value ({config_name})')
    
    #validate varying_field
    if (not field_to_vary in all_fields):
        raise ValueError(f'{field_to_vary} not a valid field')

    for new_value in desired_range:
        config = base_config.copy()
        location = base_config['location']
        if field_to_vary != 'location':
            new_config_name = f'{location}_{field_to_vary}_{new_value}'
        else:
            new_config_name = f'{new_value}'
        new_config_file_name = f'{new_config_name}.yaml'
        #update values
        config['config_name'] = new_config_file_name
        config[field_to_vary] = new_value

        #yaml path    
        file_path = os.path.join(base_config['config_set'], new_config_file_name)
        if os.path.isfile(file_path):
            raise ValueError(f'{file_path} already exists')
        #breakpoint()
        with open(file_path, 'w') as outfile:
            yaml.dump(config, outfile, default_flow_style=False, sort_keys= False)

        # Create YAML content dynamically based on the base_config
        yaml_content = generate_yaml_content(config)
        
        # Write the custom content to the YAML file
        with open(file_path, 'w') as outfile:
            outfile.write(yaml_content)

#generate files 
# generate_configs('test_configs\Richmond_city_original_2024.yaml', 'year', ['2014', '2016', '2018', '2020'])
#generate_configs('test_configs\Richmond_city_original_2024.yaml', 'precincts_open', ['14', '15', '16', '17', '18'])
#generate_configs('test_configs\Richmond_city_original_2024.yaml', 'capacity', [1.2, 1.4, 1.6, 1.8])
# generate_configs('test_configs\Richmond_city_original_2024.yaml', 'precincts_open', ['10', '11'])