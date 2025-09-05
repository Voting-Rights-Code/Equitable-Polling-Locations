''' Reusable constants '''

import os

LOCATION_SOURCE_DB = 'db'
LOCATION_SOURCE_CSV = 'csv'

RESULTS_FOLDER_NAME = 'results'

POLLING_FOLDER_NAME = 'polling'

DRIVING_FOLDER_NAME = 'driving'

DATASETS_DIR_NAME = 'datasets'

CONFIG_DIR_NAME = 'configs'

TABBLOCK_SHP_FILE_SUFFIX = 'tabblock20.shp'

BLOCK_GROUP_SHP_FILE_SUFFIX = 'bg20.shp'

CONSUS = 'census'

TIGER = 'tiger'

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))

DATASETS_DIR = os.path.join(PROJECT_ROOT_DIR, DATASETS_DIR_NAME)

RESULTS_BASE_DIR = os.path.join(DATASETS_DIR, RESULTS_FOLDER_NAME)

CONFIG_BASE_DIR = os.path.join(PROJECT_ROOT_DIR, DATASETS_DIR_NAME, CONFIG_DIR_NAME)

POLLING_DIR = os.path.join(DATASETS_DIR, POLLING_FOLDER_NAME)

DRIVING_DIR = os.path.join(DATASETS_DIR, DRIVING_FOLDER_NAME)

CENSUS_TIGER_DIR = os.path.join(DATASETS_DIR, CONSUS, TIGER)
