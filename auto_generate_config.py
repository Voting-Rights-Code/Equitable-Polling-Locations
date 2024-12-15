import yaml
import os
import argparse

from sqlalchemy import inspect, sql

import models as Models


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
    for key in input_config.keys():
        if input_config[key] is None:
            continue
        if isinstance(input_config[key], str) and isinstance(model_types[key], sql.sqltypes.String):
            continue
        if isinstance(input_config[key], list) and isinstance(model_types[key], sql.sqltypes.ARRAY):
            if len(input_config[key]) == 0:
                continue
            elif all(isinstance(x, str) for x in input_config[key]) and isinstance(model_types[key].item_type, sql.sqltypes.String):
                continue
        if isinstance(input_config[key], (int, float)) and isinstance(model_types[key], (sql.sqltypes.Float, sql.sqltypes.Integer)):
            continue
        if isinstance(input_config[key], bool) and isinstance(model_types[key], sql.sqltypes.Boolean):
            continue
        else:
            raise ValueError(f'{key} is of wrong type. See models.model_config.py for correct types.')
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

        #change the naming convention if the desired range is a list
        if isinstance(new_value, list):
            new_value_suffix = '_'.join(new_value)
            if len(new_value_suffix) > 40:
                new_value_suffix = f'{field_to_vary}_list_{desired_range.index(new_value)}'
        else:
            new_value_suffix = new_value
 
        #change the naming convention if the varying field is "location"
        if field_to_vary != 'location':
            new_config_name = f'{location}_{field_to_vary}_{new_value_suffix}'
        else:
            new_config_name = f'{new_value_suffix}'
        new_config_file_name = f'{new_config_name}.yaml'
        #update values
        config['config_name'] = new_config_name
        config[field_to_vary] = new_value

        #yaml path    
        file_path = os.path.join(base_config['config_set'], new_config_file_name)
        if os.path.isfile(file_path):
            raise ValueError(f'{file_path} already exists')
        
        with open(file_path, 'w') as outfile:
            yaml.dump(config, outfile, default_flow_style=False, sort_keys= False)


#Note this doesn't work
# if __name__ == '__main__':
#     parser = argparse.ArgumentParser()
#     parser.add_argument(
#         'base_config_path', help="File path of the .yaml file to use as the template config"
#     )
#     parser.add_argument(
#         'field_to_change', help="The config field that is to vary in for this config_set"
#     )
#     parser.add_argument(
#         'new_range', help="The set of values that field_to_change should take for this config_set"
#     )
#     args = parser.parse_args()
#     print(args)
#     generate_configs(args.base_config_path, args.field_to_change, args.new_range)



#generate files 
precinct_range = [i for i in range(15, 31)]
generate_configs('DeKalb_County_GA_no_school_penalize_bg_configs_driving_pre_EV_2024\DeKalb_GA_no_school_15.yaml_template', 'precincts_open', precinct_range)
generate_configs('DeKalb_County_GA_no_school_penalize_bg_configs_log_driving_pre_EV_2024\DeKalb_GA_no_school_15.yaml_template', 'precincts_open', precinct_range)
generate_configs('DeKalb_County_GA_no_bg_school_configs_driving_pre_EV_2024\DeKalb_GA_no_bg_school_15.yaml_template', 'precincts_open', precinct_range)
generate_configs('DeKalb_County_GA_no_bg_school_configs_log_driving_pre_EV_2024\DeKalb_GA_no_bg_school_15.yaml_template', 'precincts_open', precinct_range)
#generate_configs('test_configs\Richmond_city_original_2024.yaml', 'year', [['2014'], ['2016'], ['2018', '2020']])
#generate_configs('test_configs\Richmond_city_original_2024.yaml', 'precincts_open', ['14', '15', '16', '17', '18'])
# generate_configs('test_configs\Richmond_city_original_2024.yaml', 'capacity', [1.2, 1.4, 1.6, 1.8])
# generate_configs('test_configs\Richmond_city_original_2024.yaml', 'precincts_open', ['10', '11'])
# generate_configs('test_configs\Richmond_city_original_2024.yaml', 'fixed_capacity_site_number', [10, 11, 12])