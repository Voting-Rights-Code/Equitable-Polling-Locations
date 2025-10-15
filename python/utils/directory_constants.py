''' Reusable constants, including paths, for source and results data reads and writes. '''

import os

LOCATION_SOURCE_DB = 'db'
LOCATION_SOURCE_CSV = 'csv'

RESULTS_FOLDER_NAME = 'results'

POLLING_FOLDER_NAME = 'polling'

DRIVING_FOLDER_NAME = 'driving'

DATASETS_FOLDER_NAME = 'datasets'

CONFIG_FOLDER_NAME = 'configs'

TABBLOCK_SHP_FILE_SUFFIX = 'tabblock20.shp'

BLOCK_GROUP_SHP_FILE_SUFFIX = 'bg20.shp'

CENSUS_FOLDER_NAME = 'census'

TIGER_FOLDER_NAME = 'tiger'

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
''' The location of this constants file '''

PROJECT_ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))
''' The root of this project '''

DATASETS_DIR = os.path.join(PROJECT_ROOT_DIR, DATASETS_FOLDER_NAME)
''' The base dir for all datasets located in the project '''

RESULTS_BASE_DIR = os.path.join(DATASETS_DIR, RESULTS_FOLDER_NAME)
''' The base dir for where all results are written out to '''

CONFIG_BASE_DIR = os.path.join(PROJECT_ROOT_DIR, DATASETS_FOLDER_NAME, CONFIG_FOLDER_NAME)
''' The base dir for where all configs are located '''

POLLING_DIR = os.path.join(DATASETS_DIR, POLLING_FOLDER_NAME)
''' The base dir for where all the polling files are located '''

DRIVING_DIR = os.path.join(DATASETS_DIR, DRIVING_FOLDER_NAME)
''' The base dir for where all the dirving files are located '''

CENSUS_TIGER_DIR = os.path.join(DATASETS_DIR, CENSUS_FOLDER_NAME, TIGER_FOLDER_NAME)
''' The base dir for where all the tiger data is located '''
