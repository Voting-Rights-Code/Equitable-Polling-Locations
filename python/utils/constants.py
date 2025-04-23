''' Reusable constants '''

import os

LOCATION_SOURCE_DB = 'db'
LOCATION_SOURCE_CSV = 'csv'

RESULTS_FOLDER_NAME = 'results'

POLLING_FOLDER_NAME = 'polling'

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))

DATASETS_DIR = os.path.join(PROJECT_ROOT_DIR, 'datasets')

RESULTS_BASE_DIR = os.path.join(PROJECT_ROOT_DIR, RESULTS_FOLDER_NAME)

CONFIG_BASE_DIR = os.path.join(PROJECT_ROOT_DIR, 'datasets', 'configs')

POLLING_DIR = os.path.join(DATASETS_DIR, POLLING_FOLDER_NAME)

DRIVING_DIR = os.path.join(DATASETS_DIR, 'driving')
