''' Test for model_data. '''

# pylint: disable=line-too-long

from itertools import product

import pandas as pd
import pytest

from python.solver import model_data

from .constants import TESTING_LOCATIONS_ONLY_PATH, TEST_LOCATION, MAP_SOURCE_DATE


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
        location=driving_testing_config.location,
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

    #read in data from testing    

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


def test_clean_data(driving_testing_config, driving_locations_results_df):
    bad_types_df = driving_locations_results_df[driving_locations_results_df['location_type'].isin(driving_testing_config.bad_types)]
    num_bad_types = len(bad_types_df)
    assert num_bad_types > 0, (
        'Test data should have some bad types, but found none.'
    )

    driving_locations_results_dest_types = driving_locations_results_df['dest_type'].unique()
    print('driving_locations_results_dest_types')
    print(driving_locations_results_dest_types)

    # Check that clean_data removes bad types when for_alpha is False
    cleaned_data_df = model_data.clean_data(driving_testing_config, driving_locations_results_df, False, False)
    cleaned_data_bad_types_df = cleaned_data_df[cleaned_data_df['location_type'].isin(driving_testing_config.bad_types)]
    num_cleaned_bad_types = len(cleaned_data_bad_types_df)

    assert num_cleaned_bad_types == 0, (
        f'Expected no bad types in cleaned data, but found {num_cleaned_bad_types} bad types.'
    )

    # Check that clean_data with alpha set to true removes all location_types that contain 'Potential' or 'centroid'
    cleaned_data_with_alpha_df = model_data.clean_data(driving_testing_config, driving_locations_results_df, True, False)
    unique_location_types = cleaned_data_with_alpha_df['location_type'].unique()

    assert not any('Potential' in s or 'centroid' in s for s in unique_location_types), (
        f'Unexpected locations from clean_data with alpha set to true should not return locations that contain "Potential" or "centroid" in location_type: {unique_location_types}'
    )

    driving_locations_results_dest_types = set(driving_locations_results_df['dest_type'].unique().tolist())
    assert driving_locations_results_dest_types == set(['potential', 'polling', 'bg_centroid']), (
        "Expected 'potential', 'polling', and 'bg_centroid' to be in location data for test to continue"
    )

    cleaned_data_dest_types = cleaned_data_df['dest_type'].unique().tolist()
    assert cleaned_data_dest_types == ['potential', 'polling']


    cleaned_data_with_alpha_dest_types = cleaned_data_with_alpha_df['dest_type'].unique().tolist()
    assert cleaned_data_with_alpha_dest_types == ['polling']

