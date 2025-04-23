''' Misc utils '''

from dataclasses import dataclass
import datetime
import os
import re
from time import time
import uuid

from python.utils.constants import DRIVING_DIR, POLLING_DIR

# class RegexMatch:
#     def __init__(self, pattern: re.Match):
#         self.pattern = pattern

#     def __eq__(self, other):
#         print(f'Match {other} to {self.pattern}')
#         return re.match(self.pattern, other) is not None

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

MEMORIZED_ENV_VALUES = None

def get_env_var_or_prompt(var_name: str, default_value: str=None) -> str:
    '''
    Gets an environment variable or prompts the user for input.

    Args:
        var_name (str): The name of the environment variable.

    Returns:
        str: The value of the environment variable or the user's input.
    '''
    global MEMORIZED_ENV_VALUES
    if not MEMORIZED_ENV_VALUES:
        MEMORIZED_ENV_VALUES = {}
    value = MEMORIZED_ENV_VALUES.get(var_name) or os.environ.get(var_name)
    if not value:
        if default_value:
            prompt_default = f' [Default: {default_value}]'
        else:
            prompt_default = ''
        value = input(f'Environment variable not found for {var_name}\nPlease enter the value{prompt_default}: ')
        MEMORIZED_ENV_VALUES[var_name] = value
    return value or default_value


def build_results_file_path(result_path: str, config_name: str) -> str:
    ''' Builds the path for the optimization results csv file. '''
    return os.path.join(result_path, f'{config_name}_results.csv')

def build_precinct_summary_file_path(result_path: str, config_name: str) -> str:
    ''' Builds the path for precinct distances csv file. '''
    return os.path.join(result_path, f'{config_name}_precinct_distances.csv')

def build_residence_summary_file_path(result_path: str, config_name: str) -> str:
    ''' Builds the path for the residence distances csv file. '''
    return os.path.join(result_path, f'{config_name}_residence_distances.csv')

def build_y_ede_summary_file_path(result_path: str, config_name: str) -> str:
    ''' Builds the path for the y ede summary csv file. '''
    return os.path.join(result_path, f'{config_name}_edes.csv')


def build_locations_distance_file_path(
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
        source_file_name = f'{location}_driving_{census_year}{extension}'
    else:
        source_file_name = f'{location}_{census_year}{extension}'


    source_path = os.path.join(POLLING_DIR, location, source_file_name)

    return source_path

def build_locations_only_file_path(location: str) -> str:
    ''' Returns the path to the locations file for this config '''

    file_name = f'{location}_locations_only.csv'
    locations_only_source_file = os.path.join(POLLING_DIR, location, file_name)

    return locations_only_source_file

def build_driving_distances_file_path(census_year: str, map_source_date: str, location: str) -> str:
    ''' Returns the path to the locations file for this config '''

    # TODO implement census_year and map_source_date

    driving_file_name = f'{location}_driving_distances.csv'

    driving_distances_file = os.path.join(DRIVING_DIR, location, driving_file_name)

    return driving_distances_file
