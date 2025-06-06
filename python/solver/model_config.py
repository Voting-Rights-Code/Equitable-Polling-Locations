#######################################
#Created on 6 December 2023
#
#@author: Voting Rights Code
#######################################

''' Utils for configuring models '''
from typing import List, Literal
from dataclasses import dataclass, field

import yaml
import os
import datetime as dt

from python.utils.constants import LOCATION_SOURCE_CSV


MODEL_CONFIG_ARRAY_NAMES = ['year', 'bad_types', 'penalized_sites']
''' These PollingModelConfig variables are expected to be arrays, not None '''

@dataclass
class PollingModelConfig:
    '''
    A simple config class to run models

    Deprecation Note: This class is being replaced by the SqlAlchemy model version ModelConfig
    '''

    location: str
    '''Name of the county or city of interest'''
    year: List[str]
    '''list of years to be studied'''
    bad_types: List[str]
    '''list of location types not to be considered in this model'''
    beta: float
    '''level of inequality aversion: [-10,0], where 0 indicates indifference, and thus uses the
    mean. -2 isa good number '''
    time_limit: int
    '''How long the solver should try to find a solution'''
    penalized_sites: List[str] = field(default_factory=list)
    '''A list of locations for which the preference is to only place a polling location there
    if absolutely necessary for coverage, e.g. fire stations.'''

    precincts_open: int = None
    '''The total number of precincts to be used this year. If no
    user input is given, this is calculated to be the number of
    polling places identified in the data.'''
    maxpctnew: float = 1.0
    '''The percent on new polling places (not already defined as a
    polling location) permitted in the data. Default = 1. I.e. can replace all existing locations'''
    minpctold: float = 0
    '''The minimun number of polling places (those already defined as a
    polling location) permitted in the data. Default = 0. I.e. can replace all existing locations'''
    max_min_mult: float = 1.0
    '''A multiplicative factor for the min_max distance caluclated
    from the data. Should be >= 1. Default = 1.'''
    capacity: float = 1.0
    '''A multiplicative factor for calculating the capacity constraint. Should be >= 1.
    Default = 1.
    Note, if this is not paired with fixed_capacity_site_number, then the capacity changes as a function of number of precincts.'''

    driving: bool = False
    ''' Driving distances used if True and distance file exists in correct location '''

    log_distance: bool = False
    ''' Log of the distance (driving or haversine) computed and used in optimization if True '''

    fixed_capacity_site_number: int = None
    '''If default number of open precincts if one wants to hold the number
    #of people that can go to a location constant (as opposed to a function of the number of locations) '''

    config_name: str = None
    '''Unique name of config. Will fall back to name of file if none is supplied'''
    config_set: str = None
    '''Set of related configs that this config belongs to'''

    fixed_capacity_site_number: int = None
    '''If default number of open precincts if one wants to hold the number
    of people that can go to a location constant (as opposed to a function of the number of locations) '''

    driving: bool = False
    ''' Driving distances used if True and distance file exists in correct location '''

    commit_hash: str = None
    '''NOT CURRENTLY IN USE. Git commit under which this code was run'''
    run_time: dt.datetime = None
    '''NOT CURRENTLY IN USE. Time at which model run was initiated'''

    config_file_path: str = None
    ''' The path to the file that defines this config.  '''
    log_file_path: str = None
    ''' If specified, the location of the file to write logs to '''

    db_id: str = None
    ''' Id if this PollingModelConfig initially came from the db '''

    location_source: Literal['csv', 'db'] = LOCATION_SOURCE_CSV
    ''' Where to retrieve the location data from, either a CSV file or the database. '''

    census_year: str = None
    ''' The census year to use. '''

    maps_source_date: str = None
    ''' The date (YYYYMMDD) of the maps source to use if driving distances are used. '''

    def __post_init__(self):
        self.varnames = list(vars(self).keys()) # Not sure if this will work, let's see

    @staticmethod
    def load_config(config_yaml_path: str) -> 'PollingModelConfig':
        ''' Return an instance of RunConfig from a yaml file '''

        with open(config_yaml_path, 'r', encoding='utf-8') as yaml_file:
            # use safe_load instead load
            config = yaml.safe_load(yaml_file)

            print(f'Config: {config_yaml_path}')
            # print(json.dumps(config, indent=4))
            filtered_args = {}
            for key, value in config.items():
                #check that the keys are all in cananonical or experimental arguments.
                #this logic allows for missing fields, just not fields outside of those predefined.
                filtered_args[key] = value
            result = PollingModelConfig(**filtered_args)

            # Ensure that any None values found in arrays are set as an empty array instead
            for array_value_name in MODEL_CONFIG_ARRAY_NAMES:
                value = getattr(result, array_value_name)
                if value is None:
                    setattr(result, array_value_name, [])

            # print('Result:')
            # print(result)

            result.config_file_path = config_yaml_path
            if not result.config_name:
                result.config_name = os.path.splitext(os.path.basename(config_yaml_path))[0]
                #print(f'Config name not specified, so taking from config YAML filepath {result.config_name}; this is not recommended')
            if not result.config_set:
                result.config_set = os.path.basename(os.path.dirname(config_yaml_path))
                #print(f'Config set not specified, so taking from config YAML filepath {result.config_set}; this is not recommended')

            return result
