''' Test for model_data. '''

# pylint: disable=redefined-outer-name,line-too-long

import os
from itertools import product

import pandas as pd
import pytest

from python.solver import model_data
from python.solver.model_config import PollingModelConfig
from python.utils.constants import POLLING_DIR

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
DRIVING_TESTING_CONFIG = os.path.join(TESTS_DIR, 'testing_config_driving.yaml')
TESTING_LOCATIONS_ONLY_PATH = os.path.join(POLLING_DIR, 'testing', 'testing_locations_only.csv')

# CENSUS_YEAR_2020 = '2020'
TEST_LOCATION = 'Gwinnett_County_GA'


MAP_SOURCE_DATE='20250101'

@pytest.fixture(scope='session')
def driving_testing_config():
    return PollingModelConfig.load_config(DRIVING_TESTING_CONFIG)

@pytest.fixture(scope='session')
def driving_locations_results_df(tmp_path_factory, driving_testing_config):
    ''' Fixture to load the locations results DataFrame from the testing locations CSV. '''

    tmp_path = tmp_path_factory.mktemp('driving_locations_results_test_data')
    build_source_ouput_tmp_path = os.path.join(tmp_path, 'testing_driving_2020.csv')

    model_data.build_source(
        'csv',
        census_year=driving_testing_config.census_year,
        location=TEST_LOCATION,
        driving=driving_testing_config.driving,
        log_distance=driving_testing_config.log_distance,
        map_source_date=MAP_SOURCE_DATE,
        locations_only_path_override=TESTING_LOCATIONS_ONLY_PATH,
        output_path_override=build_source_ouput_tmp_path,
    )

    locations_results_df = model_data.load_locations_csv(build_source_ouput_tmp_path)
    return locations_results_df

def test_build_source_columns(driving_locations_results_df):
    ''' Checks that the columns in the locations_results_df match the expected columns. '''

    expected_columns = [
        'id_orig', 'id_dest', 'address', 'dest_lat', 'dest_lon', 'orig_lat',
        'orig_lon', 'location_type', 'dest_type', 'population', 'hispanic',
        'non_hispanic', 'white', 'black', 'native', 'asian', 'pacific_islander',
        'other', 'multiple_races', 'distance_m', 'source'
    ]

    actual_columns = driving_locations_results_df.columns.tolist()

    assert actual_columns == expected_columns, (
        f'Column mismatch.\n'
        f'Expected: {expected_columns}\n'
        f'Actual: {actual_columns}'
    )

def test_build_source_locations(driving_testing_config, driving_locations_results_df):
    ''' Calls build_source with driving distances and checks the locations are as expected. '''

    locations_only_df = model_data.load_locations_only_csv(TESTING_LOCATIONS_ONLY_PATH)
    # driving_locations_results_df = model_data.load_locations_csv(build_source_ouput_tmp_path)

    # Get the demographics block so we can get the expected GEO_IDs for id_orig
    demographics_block_df = model_data.get_demographics_block(
        census_year=driving_testing_config.census_year,
        location=TEST_LOCATION,
    )
    # Get the blockgroup to get the expected Locations
    blockgroup = model_data.get_blockgroup_gdf(driving_testing_config.census_year, TEST_LOCATION)

    expected_id_orig = demographics_block_df['GEO_ID'].unique().tolist()
    expected_id_dest = locations_only_df['Location'].unique().tolist() + blockgroup['Location'].unique().tolist()

    expected_permutations = set(product(expected_id_orig, expected_id_dest))

    # Check that the built locations contain all the expected id_orig and id_dest pairs
    actual_permutations = set(driving_locations_results_df[['id_orig', 'id_dest']].apply(tuple, axis=1)) #.drop_duplicates())

    assert actual_permutations == expected_permutations, (
        f'Permutations mismatch.\n'
        f'Missing permutations: {expected_permutations - actual_permutations}\n'
        f'Unexpected permutations: {actual_permutations - expected_permutations}'
    )


def test_build_source_driving_distances(driving_testing_config, driving_locations_results_df):
    ''' Checks that the driving distances in locations_results_df match those in the driving distances CSV. '''

    # Check that all locations_results_df sources are 'driving distance'
    sources = driving_locations_results_df['source'].unique().tolist()
    assert sources == ['driving distance'], f'Unexpected sources found: {sources}'

    driving_distances_df = model_data.get_csv_driving_distances(
        driving_testing_config.census_year,
        MAP_SOURCE_DATE,
        TEST_LOCATION,
    )

    loc_df_subset = driving_locations_results_df[['id_orig', 'id_dest', 'distance_m']]
    drive_df_subset = driving_distances_df[['id_orig', 'id_dest', 'distance_m']]

    merged_df = pd.merge(
        loc_df_subset,
        drive_df_subset,
        on=['id_orig', 'id_dest'],
        how='left',
        suffixes=('_loc', '_drive') # Add suffixes to distinguish distance_m columns
    )

    comparable_df = merged_df.dropna(subset=['distance_m_loc', 'distance_m_drive'])

    mismatches = []
    for _, row in comparable_df.iterrows():
        orig = row['id_orig']
        dest = row['id_dest']
        dist_loc = row['distance_m_loc']
        dist_drive = row['distance_m_drive']

        # pytest.approx handles floating point comparisons with a tolerance
        if not dist_loc == pytest.approx(dist_drive):
            mismatches.append(
                f'  (id_orig=\'{orig}\', id_dest=\'{dest}\'): '
                f'locations_results_df={dist_loc}, driving_distances_df={dist_drive}'
            )

    assert not mismatches, \
        'Distance mismatches found for the following (id_orig, id_dest) pairs:\n' + '\n'.join(mismatches)

def test_build_source_column_output(driving_locations_results_df):
    ''' Check that the coulmns from a very small sample of rows from from build_source are as expected. '''

    expected_sample = [
        {'id_orig':'131350501051000','id_dest':'Gwinnett College - Lilburn Campus','address':'4230 US-29 #11, Lilburn, GA 30047','dest_lat':33.9158499213,'dest_lon':-84.1203301157,'orig_lat':34.135637,'orig_lon':-83.9763925,'location_type':'College Campus - Potential','dest_type':'potential','population':2,'hispanic':0,'non_hispanic':2,'white':0,'black':0,'native':0,'asian':2,'pacific_islander':0,'other':0,'multiple_races':0,'distance_m':33072.52,'source':'driving distance'},
        {'id_orig':'131350501051000','id_dest':'UGA Gwinnett Campus','address':'2530 Sever Rd NW, Lawrenceville, GA 30043','dest_lat':34.0103872256,'dest_lon':-84.0729515756,'orig_lat':34.135637,'orig_lon':-83.9763925,'location_type':'College Campus - Potential','dest_type':'potential','population':2,'hispanic':0,'non_hispanic':2,'white':0,'black':0,'native':0,'asian':2,'pacific_islander':0,'other':0,'multiple_races':0,'distance_m':20726.93,'source':'driving distance'},
        {'id_orig':'131350501051000','id_dest':'E Center','address':'5019 W Broad St NE, Sugar Hill, GA 30518','dest_lat':34.1188454492,'dest_lon':-84.0336851381,'orig_lat':34.135637,'orig_lon':-83.9763925,'location_type':'Community Center - Potential','dest_type':'potential','population':2,'hispanic':0,'non_hispanic':2,'white':0,'black':0,'native':0,'asian':2,'pacific_islander':0,'other':0,'multiple_races':0,'distance_m':10919.36,'source':'driving distance'},
        {'id_orig':'131350501051000','id_dest':'Highway 78 Community Imprvmnt','address':'2463 Heritage Village # 106, Snellville, GA 30078','dest_lat':33.8734931136,'dest_lon':-84.0194951064,'orig_lat':34.135637,'orig_lon':-83.9763925,'location_type':'Community Center - Potential','dest_type':'potential','population':2,'hispanic':0,'non_hispanic':2,'white':0,'black':0,'native':0,'asian':2,'pacific_islander':0,'other':0,'multiple_races':0,'distance_m':35843.07,'source':'driving distance'},
        {'id_orig':'131350501051000','id_dest':'CHESTNUT GROVE BAPTIST CHURCH','address':'2299 ROSEBUD RD','dest_lat':33.8865127446,'dest_lon':-83.9592403865,'orig_lat':34.135637,'orig_lon':-83.9763925,'location_type':'Elec Day Church - Potential','dest_type':'potential','population':2,'hispanic':0,'non_hispanic':2,'white':0,'black':0,'native':0,'asian':2,'pacific_islander':0,'other':0,'multiple_races':0,'distance_m':31408.65,'source':'driving distance'},
        {'id_orig':'131350501051000','id_dest':'FORT DANIEL ELEMENTARY SCHOOL','address':'1725 AUBURN ROAD','dest_lat':34.0448930406,'dest_lon':-83.9233994405,'orig_lat':34.135637,'orig_lon':-83.9763925,'location_type':'Elec Day School - Potential','dest_type':'potential','population':2,'hispanic':0,'non_hispanic':2,'white':0,'black':0,'native':0,'asian':2,'pacific_islander':0,'other':0,'multiple_races':0,'distance_m':15702.33,'source':'driving distance'},
    ]

    # Set 'id_orig' and 'id_dest' as the index for easier lookup.
    df = driving_locations_results_df.set_index(['id_orig', 'id_dest'])

    for expected_row in expected_sample:
        # Extract the key for lookup from the expected row
        lookup_key = (expected_row['id_orig'], expected_row['id_dest'])

        # Check if the row exists
        assert lookup_key in df.index, f"Row with id_orig={lookup_key[0]} and id_dest='{lookup_key[1]}' not found in DataFrame."

        # Retrieve the matching row from the DataFrame
        actual_row = df.loc[lookup_key]

        # Compare all columns for the matched row
        for column_name, expected_value in expected_row.items():
            # Skip the index columns as they were used for the lookup
            if column_name in ['id_orig', 'id_dest']:
                continue

            # Get the actual value from the DataFrame row
            actual_value = actual_row[column_name]

            # For floating point numbers, use pytest.approx for safe comparison
            if isinstance(expected_value, float):
                assert actual_value == pytest.approx(expected_value), \
                    f"Mismatch in column '{column_name}' for row {lookup_key}. Expected: {expected_value}, Got: {actual_value}"
            else:
                # For all other data types, use a direct comparison
                assert actual_value == expected_value, \
                    f"Mismatch in column '{column_name}' for row {lookup_key}. Expected: {expected_value}, Got: {actual_value}"

