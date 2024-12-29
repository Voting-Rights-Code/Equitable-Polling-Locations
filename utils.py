''' Misc utils '''

from dataclasses import dataclass
import datetime
import os
import re
from time import time
import uuid



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
