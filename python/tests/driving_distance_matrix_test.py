'''Tests for python/utils/driving_distance_matrix.py.'''
import pandas as pd

from python.utils.driving_distance_matrix import (
    estimate_origin,
    get_missing_origins,
    matrix_response_to_long_df,
)


class TestGetMissingOrigins:
    '''Identify origins with any null driving distance.'''

    def test_returns_origins_with_at_least_one_null(self):
        df = pd.DataFrame({
            'id_orig': ['a', 'a', 'b', 'b', 'c'],
            'id_dest': ['x', 'y', 'x', 'y', 'x'],
            'driving_m': [10.0, None, 20.0, 30.0, None],
        })
        assert get_missing_origins(df) == {'a', 'c'}

    def test_returns_empty_set_when_none_missing(self):
        df = pd.DataFrame({
            'id_orig': ['a', 'b'],
            'id_dest': ['x', 'x'],
            'driving_m': [10.0, 20.0],
        })
        assert get_missing_origins(df) == set()


class TestMatrixResponseToLongDf:
    '''Reshape source x dest 2-D distances into a long DataFrame.'''

    def test_three_columns_id_orig_id_dest_distance_m(self):
        df = matrix_response_to_long_df(
            source_names=['a', 'b'],
            dest_names=['x', 'y'],
            distances=[[0.0, 100.0], [200.0, 0.0]],
        )
        assert set(df.columns) == {'id_orig', 'id_dest', 'distance_m'}

    def test_row_count_is_sources_times_dests(self):
        df = matrix_response_to_long_df(
            source_names=['a', 'b', 'c'],
            dest_names=['x', 'y'],
            distances=[[1, 2], [3, 4], [5, 6]],
        )
        assert len(df) == 6

    def test_values_align_with_source_dest_pairs(self):
        df = matrix_response_to_long_df(
            source_names=['a', 'b'],
            dest_names=['x', 'y'],
            distances=[[10.0, 20.0], [30.0, 40.0]],
        )
        a_x = df.loc[(df['id_orig'] == 'a') & (df['id_dest'] == 'x'), 'distance_m'].iloc[0]
        b_y = df.loc[(df['id_orig'] == 'b') & (df['id_dest'] == 'y'), 'distance_m'].iloc[0]
        assert a_x == 10.0
        assert b_y == 40.0


class TestEstimateOrigin:
    '''Snap an unroutable origin to its nearest routable haversine neighbor.

    The neighbor must be within 1000 m haversine; the estimated driving distance
    is (neighbor's driving distance) + (haversine offset).
    '''

    def test_snaps_to_nearest_within_1km(self):
        # Coordinates: ``[longitude, latitude]``.
        locations = {
            'bad': [-84.000, 33.9500],
            'good1': [-84.000, 33.9510],   # ~111 m north of bad
            'good2': [-84.005, 34.0000],   # ~5.5 km away - out of range
        }
        known_df = pd.DataFrame({
            'id_orig': ['good1', 'good1', 'good2', 'good2'],
            'id_dest': ['dest1', 'dest2', 'dest1', 'dest2'],
            'driving_m': [100.0, 200.0, 9999.0, 9998.0],
        })
        result = estimate_origin('bad', known_df, locations)
        assert set(result.columns) >= {'id_orig', 'id_dest', 'driving_m'}
        assert set(result['id_dest']) == {'dest1', 'dest2'}
        # Only good1 is in range; estimate ~ 100 + ~111 = ~211 for dest1.
        dest1_row = result[result['id_dest'] == 'dest1'].iloc[0]
        assert 200 < dest1_row['driving_m'] < 250

    def test_returns_empty_when_no_neighbor_in_range(self):
        locations = {
            'bad': [-84.000, 33.9500],
            'far_only': [-83.000, 34.5000],   # ~80 km away
        }
        known_df = pd.DataFrame({
            'id_orig': ['far_only'], 'id_dest': ['dest1'], 'driving_m': [5000.0],
        })
        result = estimate_origin('bad', known_df, locations)
        assert len(result) == 0
