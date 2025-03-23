''' Reusable constants '''

import os

RESULTS_FOLDER_NAME = 'results'

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))

DATASETS_DIR = os.path.join(PROJECT_ROOT_DIR, 'datasets')

RESULTS_BASE_DIR = os.path.join(PROJECT_ROOT_DIR, RESULTS_FOLDER_NAME)

CONFIG_BASE_DIR = os.path.join(PROJECT_ROOT_DIR, 'datasets', 'configs')
