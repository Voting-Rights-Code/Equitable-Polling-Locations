#######################################
#Created on 6 December 2023
#
#@author: Voting Rights Code
#######################################

''' Utils for configuring models '''
from typing import List, Optional, Literal, Union
from dataclasses import dataclass, field
import yaml
from pydantic import BaseModel, Field, ConfigDict

class ConfigOtherArgs(BaseModel):
    """Config class to make sure necessary distance generation parameters are specified."""

    model_config = ConfigDict(extra="allow")

    # calculation_method: str
    # """Method can be Isochrone or Direct"""
    data_source: str
    """Specifies the data source"""
    travel_method: Optional[str]
    """Must be a method supported by the specified data source. Not needed for Haversine"""
    travel_times: list = list(range(1, 41))
    # isochrone_buffer_m: float
    # """Used by some isochrone generators to provide a radius around the roads when generating shapes"""


class OsmArgs(BaseModel):
    """Config class to make sure necessary OSM parameters are specified."""

    model_config = ConfigDict(extra="ignore")

    county_buffer_m: Union[float, int] = 10000
    """The range of space around the county to pull OSM data for. This is to account for
    travel over county borders to the destination."""
    isochrone_buffer_m: Union[float, int] = 304.8
    """What buffer to apply in creating the shape once the isochrone has been calculated."""
    network_type: Literal["all", "all_public", "bike", "drive", "drive_service", "walk"]
    """Allowed OSM netowork types. E.g. drive or bike"""
    retain_all: bool = False
    """if True, return the entire graph even if it is not connected. otherwise,
    retain only the largest weakly connected component."""

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
    fixed_capacity_site_number: int = None
    '''If default number of open precincts if one wants to hold the number
    of people that can go to a location constant (as opposed to a function of the number of locations) '''
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

