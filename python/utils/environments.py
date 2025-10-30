''' A util that loads datasets from confirg '''

from dataclasses import dataclass

import os
import yaml

from .directory_constants import SETTINGS_PATH

def get_env_var_or_prompt(var_name: str, default_value: str=None, prompt: str=None) -> str:
    '''
    Gets an environment variable or prompts the user for input.

    Args:
        var_name (str): The name of the environment variable.

    Returns:
        str: The value of the environment variable or the user's input.
    '''
    value = os.environ.get(var_name)
    if not value:
        if not prompt:
            if default_value:
                prompt_default = f' [Default: {default_value}]'
            else:
                prompt_default = ''
            prompt = f'Environment variable not found for {var_name}\nPlease enter the value{prompt_default}: '
        value = input(prompt)
    return value or default_value


@dataclass
class Environment:
    ''' Environment specific variables. '''
    project: str
    dataset: str

    def __str__(self) -> str:
        return f'{self.project}/{self.dataset}'

def load_env(name: str=None) -> Environment:
    '''
        Loads a specific environment's configuration from a YAML file.

        Args:
            name: The name of the environment to load (e.g., "development").
            No value will prompt the user.

        Returns:
            An Environment dataclass instance with the loaded settings.

        Raises:
            ValueError: If the specified environment name is not found in the file.
            FileNotFoundError: If the config file at ENVIRONMENTS_PATH does not exist.
    '''

    if not os.path.isfile(SETTINGS_PATH):
        print(f'Could not find {SETTINGS_PATH}')

        raise FileNotFoundError(f'Could not find config file: {SETTINGS_PATH}')

    with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
        all_configs: dict = yaml.safe_load(f)


    env_names: list[str] = all_configs.keys()
    if len(env_names) < 1:
        raise FileNotFoundError(f'Setting file {SETTINGS_PATH} does not contain any environments')

    if not name:
        options = ', '.join(env_names)
        prompt = f'Please choose an environment from [{options}]: '
        name = get_env_var_or_prompt('ENV', prompt=prompt)

    env_config = all_configs.get(name)

    # Raise an error if the environment doesn't exist
    if not env_config:
        raise ValueError(f'Error: Environment "{name}" not found in {SETTINGS_PATH}')

    # Use dictionary unpacking to instantiate and return the dataclass
    return Environment(**env_config)
