''' Misc utils '''

from dataclasses import dataclass
import datetime
import os
import re
from time import time
import uuid

import numpy as np

from python.utils.directory_constants import (
  BLOCK_GROUP_FILE_SUFFIX, CENSUS_FOLDER_NAME, CENSUS_TIGER_DIR, 
  DATASETS_DIR, REDISTRICTING_FOLDER_NAME,
  DRIVING_DIR, POLLING_DIR, TABBLOCK_FILE_SUFFIX,
  BLOCK_GROUP_GEO, BLOCK_GEO
)

@dataclass
class RegexEqual(str):
    string: str
    match: re.Match = None

    def __eq__(self, pattern):
        self.match = re.search(pattern, self.string)
        return self.match is not None

enabled: bool = False

def set_timers_enabled(value: bool):
    global enabled
    enabled = value


def timer(func):
    # This function shows the execution time of
    # the function object passed

    def wrap_func(*args, **kwargs):
        t1 = time()
        result = func(*args, **kwargs)
        t2 = time()
        if enabled:
            print(f'Function {func.__name__!r} executed in {(t2-t1):.4f}s')
        return result
    return wrap_func


def current_time_utc() -> datetime:
    ''' Returns a date time instance of the current time in utc. '''
    return datetime.datetime.now(datetime.timezone.utc)

def log_date_prefix() -> str:
    ''' Returns a string prefix for log files based on the current date and time. '''
    return datetime.datetime.now().strftime('%Y%m%d%H%M%S')


def generate_uuid() -> str:
    ''' Returns a new uuid4 string. '''
    return str(uuid.uuid4())


def is_float(value):
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def is_int(value):
    try:
        return str(int(value)) == str(value) or f'{float(value)}' == f'{int(value)}.0'
    except (TypeError, ValueError):
        return False


def is_str(value):
    return isinstance(value, str)


def is_boolean(value):
    return isinstance(value, bool)


def build_results_file_path(result_path: str,  result_prefix: str) -> str:
    ''' Builds the path for the optimization results csv file. '''
    return os.path.join(result_path, f'{result_prefix}_results.csv')


def build_precinct_summary_file_path(result_path: str,  result_prefix: str) -> str:
    ''' Builds the path for precinct distances csv file. '''
    return os.path.join(result_path, f'{result_prefix}_precinct_distances.csv')


def build_residence_summary_file_path(result_path: str, result_prefix: str) -> str:
    ''' Builds the path for the residence distances csv file. '''
    return os.path.join(result_path, f'{result_prefix}_residence_distances.csv')


def build_y_ede_summary_file_path(result_path: str, result_prefix: str) -> str:
    ''' Builds the path for the y ede summary csv file. '''
    return os.path.join(result_path, f'{result_prefix}_edes.csv')


def build_distance_file_path(
        census_year: str,
        location: str,
        driving: bool,
        log_distance: bool,
    ) -> str:
    ''' Returns the path to the locations files that includes distances for this config '''
    if log_distance:
        extension = '_log.csv'
    else:
        extension = '.csv'

    if driving:
        distance_file_name = f'{location}_driving_distances_{census_year}{extension}'
    else:
        distance_file_name = f'{location}_distances_{census_year}{extension}'


    distance_file_path = os.path.join(POLLING_DIR, location, distance_file_name)

    return distance_file_path


def build_potential_locations_file_path(location: str) -> str:
    ''' Returns the path to the locations file for this config '''

    file_name = f'{location}_potential_locations.csv'
    potential_locations_source_file = os.path.join(POLLING_DIR, location, file_name)

    return potential_locations_source_file


# pylint: disable-next=unused-argument
def build_driving_distances_file_path(census_year: str, map_source_date: str, location: str) -> str:
    ''' Returns the path to the locations file for this config '''

    # TODO implement census_year and map_source_date

    driving_file_name = f'{location}_driving_distances.csv'

    driving_distances_file = os.path.join(DRIVING_DIR, location, driving_file_name)

    return driving_distances_file


def build_decennial_dir_path(location: str, geo: str) -> str:
    "returns the directory for the decennial block or block group data"
    
    decennial_dir = os.path.join(DATASETS_DIR, CENSUS_FOLDER_NAME, REDISTRICTING_FOLDER_NAME, location)
    if geo == BLOCK_GEO:
        pass
    elif geo == BLOCK_GROUP_GEO:
        decennial_dir = os.path.join(decennial_dir, "block group demographics")
    else:
        raise ValueError(f'geo must be either block or block group')

    return decennial_dir

def build_decennial_file_paths(census_year: str, geo: str, pnum: str, location: str, meta: bool) -> str:
    ''' Returns the path to Census data p3 or p4 table or metadata'''
    
    decennial_dir = build_decennial_dir_path(location, geo)
    
    if meta == False:
        file_name = f'DECENNIALPL{census_year}.{pnum}-Data.csv'
    else: #meta == True
        file_name = f'DECENNIALPL{census_year}.{pnum}-Column-Metadata.csv'

    return os.path.join(decennial_dir, file_name)


""" def build_p4_source_file_path(census_year: str, census_data_type: str, location: str) -> str:
    ''' Returns the path to Census data p4 table '''

    file_name_p4 = f'DECENNIALPL{census_year}.P4-Data.csv'

    demographics_dir = build_decennial_dir_path(census_data_type, location)

    return os.path.join(demographics_dir, file_name_p4)
 """

def build_tiger_location_dir(location: str) -> str:
    ''' Returns the path to the Census Tiger data for this location '''

    return os.path.join(CENSUS_TIGER_DIR, location)

def build_CVAP_source_file_path(census_year: str, census_data_type: str, location: str) -> str:
    ''' Returns the path to Census data p3 table '''

    file_name_cvap = f'CVAP_{census_year}-Data.csv'

    demographics_dir = build_decennial_dir_path(census_data_type, location)

    return os.path.join(demographics_dir, file_name_cvap)


def get_block_source_file_path(census_year, location: str) -> str:
    geography_dir = build_tiger_location_dir(location)
    file_list = os.listdir(geography_dir)

    prefix = f'tl_{census_year}_'

    file_list = [f for f in file_list if f.startswith(prefix) and f.endswith(f'{TABBLOCK_FILE_SUFFIX}.shp')]

    if not file_list:
        # pylint: disable-next=line-too-long
        raise ValueError(f'No block file matching {prefix}.*{TABBLOCK_FILE_SUFFIX}.shp found for location {location} in {geography_dir}. Reinstall using api or manually following download instruction from README.')

    block_filename = file_list[0]

    return os.path.join(geography_dir, block_filename)


def get_block_group_block_source_file_path(census_year, location: str) -> str:
    geography_dir = build_tiger_location_dir(location)
    file_list = os.listdir(geography_dir)

    prefix = f'tl_{census_year}_'

    file_list = [f for f in file_list if f.startswith(prefix) and f.endswith(f'{BLOCK_GROUP_FILE_SUFFIX}.shp')]

    if not file_list:
        # pylint: disable-next=line-too-long
        raise ValueError(f'No block group file matching {prefix}.*{BLOCK_GROUP_FILE_SUFFIX}.shp found for location {location} in {geography_dir}. Reinstall using api or manually following download instruction from README.')

    block_group_filename = file_list[0]

    return os.path.join(geography_dir, block_group_filename)


def csv_str_converter(value):
    ''' Converts a read in csv value to a string to a without the use of nan if emptry. '''
    if not value:
        return ''
    return value


def csv_float_converter(value):
    ''' Converts a read in csv value to a float, or returns None if the string is empty. '''
    if value == '':
        return np.nan
    try:
        return np.float64(value)
    except ValueError:
        raise ValueError(f'Invalid float value: {value}') from None


def csv_int_converter(value):
    ''' Converts a read in csv value to an int, or returns None if the string is empty. '''
    if value == '':
        return np.nan
    try:
        return np.int32(value)
    except ValueError:
        raise ValueError(f'Invalid int value: {value}') from None
