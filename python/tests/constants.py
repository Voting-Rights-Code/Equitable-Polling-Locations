''' Reusable constants for tests. '''

import os

from python.utils.constants import POLLING_DIR

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TESTING_LOCATIONS_ONLY_PATH = os.path.join(POLLING_DIR, 'testing', 'testing_locations_only.csv')

TEST_LOCATION = 'Gwinnett_County_GA'
MAP_SOURCE_DATE='20250101'

TESTING_CONFIG_EXPANDED = os.path.join(TESTS_DIR, 'testing_config_expanded.yaml')
TESTING_CONFIG_PENALTY = os.path.join(TESTS_DIR, 'testing_config_penalty.yaml')
DRIVING_TESTING_CONFIG = os.path.join(TESTS_DIR, 'testing_config_driving.yaml')

TESTING_LOCATIONS_ONLY_PATH = os.path.join(POLLING_DIR, 'testing', 'testing_locations_only.csv')

TEST_KP_FACTOR = os.path.join(TESTS_DIR, 'test_kp_factor.csv')
