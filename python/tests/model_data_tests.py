''' Test for model_data. '''

import os
from itertools import product

from python.solver import model_data
from python.solver.model_config import PollingModelConfig
from python.utils.constants import POLLING_DIR

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
DRIVING_TESTING_CONFIG = os.path.join(TESTS_DIR, 'testing_config_driving.yaml')
TESTING_LOCATIONS_ONLY_PATH = os.path.join(POLLING_DIR, 'testing', 'testing_locations_only.csv')

def test_build_source_with_distances(tmp_path):
    ''' Calls build_source with driving distances and checks the output. '''

    location = 'Gwinnett_County_GA'
    driving_config = PollingModelConfig.load_config(DRIVING_TESTING_CONFIG)

    build_source_ouput_tmp_path = os.path.join(tmp_path, 'testing_driving_2020.csv')

    model_data.build_source(
        'csv',
        census_year=driving_config.census_year,
        location=location,
        driving=driving_config.driving,
        log_distance=driving_config.log_distance,
        map_source_date='20250101',
        locations_only_path_override=TESTING_LOCATIONS_ONLY_PATH,
        output_path_override=build_source_ouput_tmp_path,
    )

    locations_only_df = model_data.load_locations_only_csv(TESTING_LOCATIONS_ONLY_PATH)
    locations_results_df = model_data.load_locations_csv(build_source_ouput_tmp_path)

    demographics_block_df = model_data.get_demographics_block(
        census_year=driving_config.census_year,
        location=location,
    )
    blockgroup = model_data.get_blockgroup_gdf('2020', location)

    expected_id_orig = demographics_block_df['GEO_ID'].unique().tolist()
    expected_id_dest = locations_only_df['Location'].unique().tolist() + blockgroup['Location'].unique().tolist()

    expected_permutations = set(product(expected_id_orig, expected_id_dest))
    actual_permutations = set(locations_results_df[['id_orig', 'id_dest']].apply(tuple, axis=1)) #.drop_duplicates())

    assert actual_permutations == expected_permutations, (
        f'Permutations mismatch.\n'
        f'Missing permutations: {expected_permutations - actual_permutations}\n'
        f'Unexpected permutations: {actual_permutations - expected_permutations}'
    )

    sources = locations_results_df['source'].unique().tolist()
    assert sources == ['driving distance'], f'Unexpected sources found: {sources}'

