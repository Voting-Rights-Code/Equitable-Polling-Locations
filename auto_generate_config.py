import yaml
import os
from model_config import get_canonical_config_args

# Define experimental fields
EXPERIMENTAL_FIELDS = ['driving', 'fixed_capacity_site_number']

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

def generate_configs(base_config_file:str, field_to_vary:str, desired_range: list, other_args = EXPERIMENTAL_FIELDS):
    """
    Generate YAML configurations by varying specified parameters while keeping others constant.
    """
    # Load the base configuration from the file
    base_config = load_base_config(base_config_file)
    
    # List of required fields that must be present in the base config
    db_fields = get_canonical_config_args(True)
    required_fields = [field for field in db_fields if not isinstance(field, list)]
    all_fields = required_fields + other_args
    
    # Validate the base config for correct fields
    config_fields = base_config.keys()
    missing_fields = set(required_fields).difference(set(config_fields))
    extra_fields = set(config_fields).difference(all_fields)
    
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
        
        ''' #Create YAML content with comments
        yaml_content = (
            "#Constants for the optimization function#\n"
            f"location: {config['location']}\n"
            "year:\n"
            f"  - '{config['year']}'\n"
            "bad_types:\n"
            + "\n".join([f"    - {bad_type}" for bad_type in config['bad_types']]) + "\n"
            f"beta: {config['beta']}\n"
            f"time_limit: {config['time_limit']} # in minutes\n"
            f"capacity: {config['capacity']}\n"
            "\n"
            "####Optional#####\n"
            f"penalized_sites: {config['penalized_sites'] or 'null'}\n"
            f"precincts_open: {config['precincts_open'] or 'null'}\n"
            f"max_min_mult: {config['max_min_mult']} # scalar >= 1\n"
            f"maxpctnew: {config['maxpctnew']} # in interval [0,1]\n"
            f"minpctold: {config['minpctold']} # in interval [0,1]\n"
            "\n"
            "####MetaData####\n"
            f"commit_hash: {config['commit_hash'] or 'null'}\n"
            f"config_name: {config['config_name'] or 'null'}\n"
            f"config_set: {config['config_set'] or 'null'}\n"
            f"run_time: {config['run_time'] or 'null'}\n"
            "\n"
            "####ExperimentalData####\n"
        )
        for field in EXPERIMENTAL_FIELDS:
            yaml_content += f"{field}: {config.get(field, 'null')}\n"

        # Write the custom content to the YAML file
        with open(file_path, 'w') as outfile:
            outfile.write(yaml_content) '''

#generate files 
# generate_configs('test_configs\Richmond_city_original_2024.yaml', 'year', ['2014', '2016', '2018', '2020'])
#generate_configs('test_configs\Richmond_city_original_2024.yaml', 'precincts_open', ['14', '15', '16', '17', '18'])
generate_configs('test_configs\Richmond_city_original_2024.yaml', 'capacity', [1.2, 1.4, 1.6, 1.8])