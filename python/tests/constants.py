''' Reusable constants for tests. '''

import os

from python.utils.constants import POLLING_DIR, CONFIG_BASE_DIR, RESULTS_BASE_DIR

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TESTING_LOCATIONS_ONLY_PATH = os.path.join(POLLING_DIR, 'testing', 'testing_locations_only.csv')

TEST_LOCATION = 'Gwinnett_County_GA'
MAP_SOURCE_DATE='20250101'

TESTING_CONFIG_DIR = os.path.join(CONFIG_BASE_DIR, 'testing')
TESTING_RESULTS_DIR = os.path.join(RESULTS_BASE_DIR, 'testing')

TESTING_CONFIG_BASE = os.path.join(TESTING_CONFIG_DIR, 'testing_config_no_bg_school.yaml')
TESTING_CONFIG_KEEP = os.path.join(TESTING_CONFIG_DIR, 'testing_config_no_bg.yaml')
TESTING_CONFIG_EXCLUDE = os.path.join(TESTING_CONFIG_DIR, 'testing_config_no_bg_campus_fire.yaml')
TESTING_CONFIG_PENALTY = os.path.join(TESTING_CONFIG_DIR, 'testing_config_penalty.yaml')
TESTING_CONFIG_PENALTY_UNUSED = os.path.join(TESTING_CONFIG_DIR, 'testing_config_penalty_school.yaml')
DRIVING_TESTING_CONFIG = os.path.join(TESTING_CONFIG_DIR, 'testing_config_driving.yaml')

TESTING_LOCATIONS_ONLY_PATH = os.path.join(POLLING_DIR, 'testing', 'testing_locations_only.csv')

TEST_KP_FACTOR = os.path.join(TESTS_DIR, 'test_kp_factor.csv')
