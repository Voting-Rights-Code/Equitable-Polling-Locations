''' Reusable constants '''

import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, '..', '..'))

DATASETS_DIR = os.path.join(PROJECT_ROOT_DIR, 'datasets')

RESULTS_BASE_DIR = os.path.join(PROJECT_ROOT_DIR, 'datasets')
