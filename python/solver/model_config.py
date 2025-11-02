#######################################
#Created on 6 December 2023
#
#@author: Voting Rights Code
#######################################

''' Utils for configuring models '''
from typing import List, Literal
from dataclasses import dataclass, field, fields, MISSING

import yaml
import datetime as dt

from python.solver.constants import DATA_SOURCE_CSV
from .constants import (
    CONFIG_DB_ID, CONFIG_COMMIT_HASH, CONFIG_RUN_TIME, CONFIG_FILE_PATH, CONFIG_LOG_FILE_PATH,
    CONFIG_MAP_SOURCE_DATE, CONFIG_LOCATION_SOURCE, CONFIG_YEAR, CONFIG_BAD_TYPES, CONFIG_PENALIZED_SITES,
)

MODEL_CONFIG_ARRAY_NAMES = [CONFIG_YEAR, CONFIG_BAD_TYPES, CONFIG_PENALIZED_SITES]
''' These PollingModelConfig variables are expected to be arrays, not None '''

NON_EMPTY_ARRAYS = [CONFIG_YEAR]
''' These PollingModelConfig variables are expected to be non-empty arrays. '''

# For now map_source_date is not required, map_source_date is for future proofing
IGNORE_ON_LOAD = [
    CONFIG_DB_ID, CONFIG_COMMIT_HASH, CONFIG_RUN_TIME, CONFIG_FILE_PATH,
    CONFIG_LOG_FILE_PATH, CONFIG_MAP_SOURCE_DATE, CONFIG_LOCATION_SOURCE,
]

@dataclass
class PollingModelConfig:
    '''
    A simple config class to run models

    Deprecation Note: This class is being replaced by the SqlAlchemy model version ModelConfig
    '''

    config_name: str
    '''Unique name of config. Will fall back to name of file if none is supplied'''
    config_set: str
    '''Set of related configs that this config belongs to'''
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
    census_year: str
    ''' The census year to use. '''

    precincts_open: int
    '''The total number of precincts to be used this year. If no
    user input is given, this is calculated to be the number of
    polling places identified in the data.'''
    maxpctnew: float
    '''The percent on new polling places (not already defined as a
    polling location) permitted in the data. '''
    minpctold: float
    '''The minimun number of polling places (those already defined as a
    polling location) permitted in the data. '''
    max_min_mult: float
    '''A multiplicative factor for the min_max distance caluclated
    from the data. Should be >= 2. '''
    capacity: float
    '''A multiplicative factor for calculating the capacity constraint. Should be >= 1.
    Note, if this is not paired with fixed_capacity_site_number, then the capacity
    changes as a function of number of precincts.'''

    fixed_capacity_site_number: int
    '''If default number of open precincts if one wants to hold the number
    #of people that can go to a location constant (as opposed to a function of the number of locations) '''

    fixed_capacity_site_number: int
    '''If default number of open precincts if one wants to hold the number
    of people that can go to a location constant (as opposed to a function of the number of locations) '''

    driving: bool
    ''' Driving distances used if True and distance file exists in correct location '''

    penalized_sites: List[str] = field(default_factory=list)
    '''A list of locations for which the preference is to only place a polling location there
    if absolutely necessary for coverage, e.g. fire stations.'''

    driving: bool = False
    ''' Driving distances used if True and distance file exists in correct location '''

    log_distance: bool = False
    ''' Log of the distance (driving or haversine) computed and used in optimization if True '''

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

    location_source: Literal['csv', 'db'] = DATA_SOURCE_CSV
    ''' Where to retrieve the location data from, either a CSV file or the database. '''

    map_source_date: str = None
    ''' The date (YYYYMMDD) of the maps source to use if driving distances are used. '''

    def __post_init__(self):
        self.varnames = list(vars(self).keys()) # Not sure if this will work, let's see

    @classmethod
    def load_config(cls, config_yaml_path: str) -> 'PollingModelConfig':
        ''' Return an instance of RunConfig from a yaml file '''

        allowed_fields = set([f.name for f in fields(cls)]) - set(IGNORE_ON_LOAD)
        required_fields = set([
            f.name
            for f in fields(cls)
            if f.default is MISSING and f.default_factory is MISSING
        ]) - set(IGNORE_ON_LOAD)

        with open(config_yaml_path, 'r', encoding='utf-8') as yaml_file:
            # use safe_load instead load
            config = yaml.safe_load(yaml_file)

            print(f'Config: {config_yaml_path}')
            # print(json.dumps(config, indent=4))

            # Confirm that all fields were loaded from the config file
            missing_fields: list[str] =[]
            for required_field in required_fields:
                if required_field not in config:
                    missing_fields.append(required_field)
            if len(missing_fields) > 0:
                raise ValueError(f'Config file {config_yaml_path} is missing the following fields: {missing_fields}.')

            unknown_fields: list[str] =[]
            for key, value in config.items():
                if key not in allowed_fields:
                    unknown_fields.append(key)
            if len(unknown_fields) > 0:
                raise ValueError(f'Config file {config_yaml_path} contains unknown fields: {unknown_fields}.')

            for key in NON_EMPTY_ARRAYS:
                array_value = config.get(key)
                if not isinstance(array_value, list) or len(array_value) == 0:
                    # pylint: disable-next=line-too-long
                    raise ValueError(f'Config file {config_yaml_path} must specify at least one value for array field {key}.')

            result = PollingModelConfig(**config)

            # Ensure that any None values found in arrays are set as an empty array instead
            for array_value_name in MODEL_CONFIG_ARRAY_NAMES:
                value = getattr(result, array_value_name)
                if value is None:
                    setattr(result, array_value_name, [])

            result.config_file_path = config_yaml_path
            if not result.config_name:
                raise ValueError(f'config_name not specified in {config_yaml_path}.')
            if not result.config_set:
                raise ValueError(f'config_set not specified in {config_yaml_path}.')

            return result
