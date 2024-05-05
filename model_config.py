#######################################
#Created on 6 December 2023
#
#@author: Voting Rights Code
#######################################

''' Utils for configuring models '''
from typing import List
from dataclasses import dataclass
import yaml

@dataclass
class PollingModelConfig:
    ''' A simple config class to run models '''

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
    Default = 1.'''
    result_folder: str = None
    ''' The location to write out results '''

    config_file_path: str = None
    ''' The path to the file that defines this config.  '''

    log_file_path: str = None
    ''' If specified, the location of the file to write logs to '''

    driving: bool = False
    ''' Driving distances used if True and distance file exists in correct location '''
    
    def __post_init__(self):
        if not self.result_folder:
            self.result_folder = f'{self.location}_results'

    @staticmethod
    def load_config(config_yaml_path: str) -> 'PollingModelConfig':
        ''' Return an instance of RunConfig from a yaml file '''

        with open(config_yaml_path, 'r', encoding='utf-8') as yaml_file:
            # use safe_load instead load
            config = yaml.safe_load(yaml_file)
            result = PollingModelConfig(**config)
            result.config_file_path = config_yaml_path
            return result

