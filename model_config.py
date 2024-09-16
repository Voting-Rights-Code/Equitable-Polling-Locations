#######################################
#Created on 6 December 2023
#
#@author: Voting Rights Code
#######################################

''' Utils for configuring models '''
from typing import List
from dataclasses import dataclass, field
import yaml
import os
import pandas as pd
import datetime as dt
import warnings
from google.cloud import bigquery 



def get_cannonical_config_args(server:bool = True):
    '''Return a list of cannonical config arguments'''

    # These should be sourced from the server
    if(server == True):
        project = "equitable-polling-locations"
        dataset = "polling"
        project_dataset = project + "." + dataset

        query = f'''
        SELECT *
        FROM {dataset}.configs
        LIMIT 1
        '''

        client = bigquery.Client()
        sample_df = client.query(query).to_dataframe()

        out = list(sample_df.columns)

    # However, if someone's running a local-only optimization, we'll return a hardcoded fallback list
    elif(server == False):
        warnings.warn('Using hardcoded list of cannonical arguments; these may be wrong and should be validated.')

        hardcoded_fallback = ['location', 'year', 'bad_types', 'beta', 'time_limit', 'capacity', 'precincts_open', 
        'max_min_mult', 'maxpctnew', 'minpctold','penalized_sites', 'config_name','config_set', 
        'result_folder', 'config_file_path', 'log_file_path']
        out = hardcoded_fallback

    return(out)


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

    fixed_capacity_site_number: int = None
    '''If default number of open precincts if one wants to hold the number
    #of people that can go to a location constant (as opposed to a function of the number of locations) '''
    
    config_name: str = None
    '''Unique name of config. Will fall back to name of file if none is supplied'''
    config_set: str = None
    '''Set of related configs that this config belongs to'''


    # NOT SUPPORTED IN PROD, CSV ONLY. Access via other_args
    #fixed_capacity_site_number: int = None
    #'''If default number of open precincts if one wants to hold the number
    #of people that can go to a location constant (as opposed to a function of the number of locations) '''
    
    # NOT SUPPORTED IN PROD, CSV ONLY. Access via other_args
    #driving: bool = False
    #''' Driving distances used if True and distance file exists in correct location '''
    
    commit_hash: str = None
    '''NOT CURRENTLY IN USE. Git commit under which this code was run'''
    run_time: dt.datetime = None
    '''NOT CURRENTLY IN USE. Time at which model run was initiated'''
    
    result_folder: str = None
    ''' The location to write out results '''
    config_file_path: str = None
    ''' The path to the file that defines this config.  '''
    log_file_path: str = None
    ''' If specified, the location of the file to write logs to '''

    other_args: dict = None
    ''' Unspecified other args, allowed only for writing to test database or CSV (not prod database) '''

    def __post_init__(self):
        if not self.result_folder:
            self.result_folder = f'{self.location}_results'
        self.varnames = list(vars(self).keys()) # Not sure if this will work, let's see

    @staticmethod
    def load_config(config_yaml_path: str, outtype: str = 'prod') -> 'PollingModelConfig':
        ''' Return an instance of RunConfig from a yaml file '''

        # Get a list of cannonical arguments from BigQuery
        server = (outtype in ['test', 'prod'])
        cannonical_args = get_cannonical_config_args(server)

        with open(config_yaml_path, 'r', encoding='utf-8') as yaml_file:
            # use safe_load instead load
            config = yaml.safe_load(yaml_file)

            filtered_args = {}
            other_args = {}
            for key, value in config.items():
                if key not in cannonical_args:
                    other_args[key] = value
                else:
                    filtered_args[key] = value
            filtered_args['other_args'] = other_args

            result = PollingModelConfig(**filtered_args)

            if(((not result.config_name) | (not result.config_set)) & (not result.config_file_path)):
                result.config_file_path = config_yaml_path
            if not result.config_name:
                result.config_name = os.path.splitext(os.path.basename(config_yaml_path))[0]
                print("Config name not specified, so taking from config YAML filepath; this is not recommended")
            if not result.config_set:
                result.config_set = os.path.basename(os.path.dirname(config_yaml_path))
                print("Config set not specified, so taking from config YAML filepath; this is not recommended")

            return result


    def df(self) -> pd.DataFrame:
        config_dict = {}
        for key, value in vars(self).items():
            config_dict[key] = [value]
        config_df = pd.DataFrame(config_dict)

        col_order = ['location', 'year', 'bad_types', 'beta', 'time_limit', 'capacity', 'precincts_open', 'max_min_mult', 'maxpctnew', 'minpctold', 'config_name','config_set' ,'commit_hash','run_time']
        config_df = config_df.loc[:, col_order]
        return config_df



    def df(self) -> pd.DataFrame:
        config_dict = {}
        for key, value in vars(self).items():
            config_dict[key] = [value]
        config_df = pd.DataFrame(config_dict)

        col_order = ['location', 'year', 'bad_types', 'beta', 'time_limit', 'capacity', 'precincts_open', 'max_min_mult', 'maxpctnew', 'minpctold', 'config_name','config_set' ,'commit_hash','run_time']
        config_df = config_df.loc[:, col_order]
        return config_df