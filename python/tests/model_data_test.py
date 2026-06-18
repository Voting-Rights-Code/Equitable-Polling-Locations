''' Test for model_data. '''

# pylint: disable=line-too-long,invalid-name
# invalid-name: CVAP is an established acronym used throughout the codebase.

from itertools import product
from unittest.mock import patch

import pandas as pd
import pytest

from python.solver import model_data
from python.solver.constants import (
    CEN20_GEO_ID,
    DISTANCE_ID_ORIG, DISTANCE_ID_DEST, DISTANCE_ADDRESS,
    DISTANCE_DEST_LAT, DISTANCE_DEST_LON, DISTANCE_ORIG_LAT, DISTANCE_ORIG_LON,
    DISTANCE_LOCATION_TYPE, DISTANCE_DEST_TYPE,
    DISTANCE_OTHER, DEMOGRAPHICS_OUTPUT_COLUMNS, DISTANCE_DEMOGRAPHICS_COLUMNS,
    DISTANCE_DISTANCE_M, DISTANCE_SOURCE,
)

from .constants import TESTING_POTENTIAL_LOCATIONS_PATH, TESTING_DRIVING_DISTANCES_PATH, TEST_LOCATION, MAP_SOURCE_DATE


def test_build_source_columns(location_df_with_driving):
    ''' Checks that the columns in the location_df_driving match the expected columns. '''

    expected_columns = set(DISTANCE_DEMOGRAPHICS_COLUMNS) | {
        DISTANCE_ID_ORIG, DISTANCE_ID_DEST, DISTANCE_ADDRESS,
        DISTANCE_DEST_LAT, DISTANCE_DEST_LON, DISTANCE_ORIG_LAT, DISTANCE_ORIG_LON,
        DISTANCE_LOCATION_TYPE, DISTANCE_DEST_TYPE,
        DISTANCE_DISTANCE_M, DISTANCE_SOURCE,
    }

    actual_columns = set(location_df_with_driving.columns)

    assert actual_columns == expected_columns, (
        f'Column mismatch.\n'
        f'Missing: {expected_columns - actual_columns}\n'
        f'Unexpected: {actual_columns - expected_columns}'
    )


def test_build_source_locations(testing_config_driving, location_df_with_driving):
    ''' Calls build_source with driving distances and checks the locations are as expected. '''

    potential_locations_df = model_data.load_potential_locations_csv(TESTING_POTENTIAL_LOCATIONS_PATH)
    # location_df_with_driving = model_data.load_locations_csv(build_source_ouput_tmp_path)

    # Get the demographics block so we can get the expected GEO_IDs for id_orig
    demographics_block_df = model_data.get_demographics_block(
        census_year=testing_config_driving.census_year,
        location=testing_config_driving.location,
        census_data_type=testing_config_driving.census_data_type,
    )
    # Get the blockgroup to get the expected Locations
    blockgroup = model_data.get_blockgroup_gdf(testing_config_driving.census_year, TEST_LOCATION)

    expected_id_orig = demographics_block_df['GEO_ID'].unique().tolist()
    expected_id_dest = potential_locations_df['Location'].unique().tolist() + blockgroup['Location'].unique().tolist()

    expected_permutations = set(product(expected_id_orig, expected_id_dest))

    # Check that the built locations contain all the expected id_orig and id_dest pairs
    actual_permutations = set(location_df_with_driving[['id_orig', 'id_dest']].apply(tuple, axis=1)) #.drop_duplicates())

    assert actual_permutations == expected_permutations, (
        f'Permutations mismatch.\n'
        f'Missing permutations: {expected_permutations - actual_permutations}\n'
        f'Unexpected permutations: {actual_permutations - expected_permutations}'
    )

    assert location_df_with_driving['orig_lat'].notna().all(), 'orig_lat should not have null values'
    assert location_df_with_driving['orig_lon'].notna().all(), 'orig_lon should not have null values'


def test_build_source_driving_distances(testing_config_driving, location_df_with_driving):
    ''' Checks that the driving distances in location_df_driving match those in the driving distances CSV. '''

    # Check that all location_df_driving sources are 'driving distance'
    sources = location_df_with_driving['source'].unique().tolist()
    assert sources == ['driving distance'], f'Unexpected sources found: {sources}'

    driving_distances_df = model_data.get_csv_driving_distances(
        testing_config_driving.census_year,
        MAP_SOURCE_DATE,
        TEST_LOCATION,
    )

    loc_df_subset = location_df_with_driving[['id_orig', 'id_dest', 'distance_m']]
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
                f'location_df_driving={dist_loc}, driving_distances_df={dist_drive}'
            )

    assert not mismatches, \
        'Distance mismatches found for the following (id_orig, id_dest) pairs:\n' + '\n'.join(mismatches)

def test_build_source_column_output(location_df_with_driving):
    ''' Checks the distances in location_df_with_driving against those store in testing_driving_distances '''

    #read in driving distance data
    from_csv = model_data.load_driving_distances_csv(TESTING_DRIVING_DISTANCES_PATH)

    # Select 'id_orig' and 'id_dest' and 'distance_m' from build source to compare
    df = location_df_with_driving[['id_orig', 'id_dest', 'distance_m']]

    #merge for comparison
    merged_data = pd.merge(from_csv, df, on = ['id_orig', 'id_dest'], suffixes = ('_from_csv', '_from_test' ))

    divergence = merged_data[merged_data['distance_m_from_csv'] != merged_data['distance_m_from_test']]

    assert divergence.shape[0] == 0, (f'the following origin, destination pairs have differing distances in the test and stored dataframes: {divergence}')

def test_clean_data(testing_config_driving, location_df_with_driving):
    bad_types_df = location_df_with_driving[location_df_with_driving['location_type'].isin(testing_config_driving.bad_types)]
    num_bad_types = len(bad_types_df)
    assert num_bad_types > 0, (
        'Test data should have some bad types, but found none.'
    )

    driving_locations_results_dest_types = location_df_with_driving['dest_type'].unique()
    print('driving_locations_results_dest_types')
    print(driving_locations_results_dest_types)

    # Check that clean_data removes bad types when for_alpha is False
    cleaned_data_df = model_data.filter_distance_data(testing_config_driving, location_df_with_driving, False, False)
    cleaned_data_bad_types_df = cleaned_data_df[cleaned_data_df['location_type'].isin(testing_config_driving.bad_types)]
    num_cleaned_bad_types = len(cleaned_data_bad_types_df)

    assert num_cleaned_bad_types == 0, (
        f'Expected no bad types in cleaned data, but found {num_cleaned_bad_types} bad types.'
    )

    # Check that clean_data with alpha set to true removes all location_types that contain 'Potential' or 'centroid'
    cleaned_data_with_alpha_df = model_data.filter_distance_data(testing_config_driving, location_df_with_driving, True, False)
    unique_location_types = cleaned_data_with_alpha_df['location_type'].unique()

    assert not any('Potential' in s or 'centroid' in s for s in unique_location_types), (
        f'Unexpected locations from clean_data with alpha set to true should not return locations that contain "Potential" or "centroid" in location_type: {unique_location_types}'
    )

    driving_locations_results_dest_types = set(location_df_with_driving['dest_type'].unique().tolist())
    assert driving_locations_results_dest_types == set(['potential', 'polling', 'bg_centroid']), (
        "Expected 'potential', 'polling', and 'bg_centroid' to be in location data for test to continue"
    )

    cleaned_data_dest_types = cleaned_data_df['dest_type'].unique().tolist()
    assert cleaned_data_dest_types == ['potential', 'polling']


    cleaned_data_with_alpha_dest_types = cleaned_data_with_alpha_df['dest_type'].unique().tolist()
    assert cleaned_data_with_alpha_dest_types == ['polling']


class TestGetCVAPDemographics:
    ''' Unit tests for model_data.get_CVAP_demographics using the committed testing fixture. '''

    def test_output_columns_are_exactly_right(self):
        ''' Returned DataFrame has exactly the shared distance schema columns — no raw CVAP names survive. '''
        result = model_data.get_CVAP_demographics('2020', 'testing')
        assert set(result.columns) == DEMOGRAPHICS_OUTPUT_COLUMNS

    def test_other_race_column_is_all_nan(self):
        ''' CVAP has no Other race category; the column must be fully NaN so downstream math is not silently wrong. '''
        result = model_data.get_CVAP_demographics('2020', 'testing')
        assert result[DISTANCE_OTHER].isna().all()

    def test_geoid_is_string_dtype(self):
        ''' GEO_ID must be string so merges on this column do not silently fail due to int/str type mismatch. '''
        result = model_data.get_CVAP_demographics('2020', 'testing')
        assert pd.api.types.is_string_dtype(result[CEN20_GEO_ID])

    def test_missing_file_raises_value_error(self):
        ''' A clear ValueError is raised when the CVAP directory exists but the requested year file does not. '''
        with pytest.raises(ValueError, match='CVAP data not found'):
            model_data.get_CVAP_demographics('2019', 'testing')

    def test_missing_directory_triggers_pull_CVAP_data(self):
        ''' pull_CVAP_data is called when the CVAP directory does not exist. '''
        with patch('python.solver.model_data.os.path.exists', return_value=False), \
             patch('python.solver.model_data.pull_CVAP_data') as mock_pull, \
             pytest.raises(ValueError):
            model_data.get_CVAP_demographics('2020', 'Gwinnett_County_GA')
        mock_pull.assert_called_once_with('GA', 'Gwinnett County', '2020')


class TestGetRedistrictingDemographics:
    ''' Unit tests for model_data.get_redistricting_demographics using the committed testing fixture. '''

    def test_output_columns_are_exactly_right(self):
        ''' Returned DataFrame has exactly the shared distance schema columns — no raw census names survive. '''
        result = model_data.get_redistricting_demographics('2020', 'testing')
        assert set(result.columns) == DEMOGRAPHICS_OUTPUT_COLUMNS

    def test_missing_file_raises_value_error(self):
        ''' A clear ValueError is raised when the redistricting directory exists but the requested year file does not. '''
        with pytest.raises(ValueError, match='P3 not found'):
            model_data.get_redistricting_demographics('2019', 'testing')

    def test_missing_directory_triggers_pull_census_data(self):
        ''' pull_census_data is called when the redistricting directory does not exist. '''
        with patch('python.solver.model_data.os.path.exists', return_value=False), \
             patch('python.solver.model_data.pull_census_data') as mock_pull, \
             pytest.raises(ValueError):
            model_data.get_redistricting_demographics('2020', 'Gwinnett_County_GA')
        mock_pull.assert_called_once_with('GA', 'Gwinnett County', '2020')

