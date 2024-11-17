import yaml
import os
#from model_config import (get_canonical_config_args, EXPERIMENTAL_FIELDS, NON_CONFIG_META_DATA)
import models as Models
from sqlalchemy import inspect


def load_base_config(config_file):
    '''Load the base configuration from the provided YAML file.'''
    with open(config_file, 'r') as file: 
        return yaml.safe_load(file)

def check_model_fields_match_input(input_config, model_inspect):
    '''Check the input field names against sql_alchemy_model'''

    #1. get model fields
    nullable_model_fields = [column.name for column in model_inspect.columns if column.nullable]
    #TODO: This is hard coding. Should fix.
    name_and_set = [column.name for column in model_inspect.columns if 'config' in column.name]
    model_fields = nullable_model_fields + name_and_set
    
    #2. get config fields
    input_fields = input_config.keys()
    
    #3. check fields the same
    missing_fields = set(model_fields).difference(set(input_fields))
    extra_fields = set(input_fields).difference(set(model_fields))
    
    #raise error as necessary
    if len(model_fields) != len(set(model_fields)):
        raise ValueError('There are repeated fields in the defined config model')
    if len(input_fields) != len(set(input_fields)):
       raise ValueError('There are repeated fields in the config file given as input')
    if len(missing_fields) >0:
        raise ValueError(f'missing required fields: {missing_fields}')
    if len(extra_fields) >0:
        raise ValueError(f'unknown fields provided: {extra_fields}')
    return

def check_model_and_input_types_match(input_config, model_inspect):
    '''Check that the types of the input config are of the correct type for the sql_alchemy model'''

    model_types = {column.name:column.type for column in model_inspect.columns} 
    input_config_types = {key:type(value) for key, value in input_config.items()} 
    breakpoint()
    #TODO: @Chad, how do I check that the types of entries in the base_config file are the same as the types of the entries in the sql_alchemy model.
    return

def generate_configs(base_config_file:str, field_to_vary:str, desired_range: list):
    """
    Generate YAML configurations by varying specified parameters while keeping others constant.
    """
    # Load the base configuration from the file
    base_config = load_base_config(base_config_file)
    
    #get sql_alchemy model for config data
    sql_alchemy_config_model = inspect(Models.ModelConfig)

    #Check that the fields in the config file match the sql model
    check_model_fields_match_input(base_config, sql_alchemy_config_model)
    
    #check that the fields of the same type
    check_model_and_input_types_match(base_config, sql_alchemy_config_model)
    

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
    if (not field_to_vary in base_config.keys()):
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
        
        with open(file_path, 'w') as outfile:
            yaml.dump(config, outfile, default_flow_style=False, sort_keys= False)

        # Create YAML content dynamically based on the base_config
        #yaml_content = generate_yaml_content(config)
        
        # Write the custom content to the YAML file
        #with open(file_path, 'w') as outfile:
        #    outfile.write(yaml_content)

#generate files 
generate_configs('test_configs\Richmond_city_original_2024.yaml', 'year', ['2014', '2016', ['2018', '2020']])
#generate_configs('test_configs\Richmond_city_original_2024.yaml', 'precincts_open', ['14', '15', '16', '17', '18'])
# generate_configs('test_configs\Richmond_city_original_2024.yaml', 'capacity', [1.2, 1.4, 1.6, 1.8])
# generate_configs('test_configs\Richmond_city_original_2024.yaml', 'precincts_open', ['10', '11'])
# generate_configs('test_configs\Richmond_city_original_2024.yaml', 'fixed_capacity_site_number', [10, 11, 12])