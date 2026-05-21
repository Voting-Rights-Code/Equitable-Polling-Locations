'''Tests for python/utils/driving_distance_matrix.py.'''
from unittest.mock import patch

import pandas as pd

from python.utils.driving_distance_matrix import (
    MATRIX_CELL_LIMIT,
    build_distance_matrix,
    estimate_origin,
    get_missing_origins,
    matrix_response_to_long_df,
    resume_from_partial_output,
)
from python.utils.ors_client import OrsMatrixError


class TestGetMissingOrigins:
    '''Identify origins with any null driving distance.'''

    def test_returns_origins_with_at_least_one_null(self):
        df = pd.DataFrame({
            'id_orig': ['a', 'a', 'b', 'b', 'c'],
            'id_dest': ['x', 'y', 'x', 'y', 'x'],
            'distance_m': [10.0, None, 20.0, 30.0, None],
        })
        assert get_missing_origins(df) == {'a', 'c'}

    def test_returns_empty_set_when_none_missing(self):
        df = pd.DataFrame({
            'id_orig': ['a', 'b'],
            'id_dest': ['x', 'x'],
            'distance_m': [10.0, 20.0],
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
            'distance_m': [100.0, 200.0, 9999.0, 9998.0],
        })
        result = estimate_origin('bad', known_df, locations)
        assert set(result.columns) >= {'id_orig', 'id_dest', 'distance_m'}
        assert set(result['id_dest']) == {'dest1', 'dest2'}
        # Only good1 is in range; estimate ~ 100 + ~111 = ~211 for dest1.
        dest1_row = result[result['id_dest'] == 'dest1'].iloc[0]
        assert 200 < dest1_row['distance_m'] < 250

    def test_returns_empty_when_no_neighbor_in_range(self):
        locations = {
            'bad': [-84.000, 33.9500],
            'far_only': [-83.000, 34.5000],   # ~80 km away
        }
        known_df = pd.DataFrame({
            'id_orig': ['far_only'], 'id_dest': ['dest1'], 'distance_m': [5000.0],
        })
        result = estimate_origin('bad', known_df, locations)
        assert len(result) == 0


class TestBuildDistanceMatrix:
    '''Top-level orchestration: batch, retry, snap, reshape.'''

    @patch('python.utils.driving_distance_matrix.query_matrix')
    def test_returns_long_form_for_single_batch(self, mock_query):
        mock_query.return_value = [[0.0, 100.0], [200.0, 0.0]]
        locations = {'a': [-84.0, 33.9], 'b': [-84.1, 34.0]}
        result = build_distance_matrix(
            locations=locations,
            source_ids=['a'],
            dest_ids=['b'],
            matrix_url='http://ors:8080/ors/v2/matrix/driving-car',
        )
        assert set(result.columns) == {'id_orig', 'id_dest', 'distance_m'}
        # Only the 'a' -> 'b' pair is asked for; the helper requests only that pair.
        assert len(result) == 1

    @patch('python.utils.driving_distance_matrix.query_matrix')
    def test_batches_when_sources_exceed_cell_limit(self, mock_query):
        # 5 destinations x batch size N must keep cells <= MATRIX_CELL_LIMIT (2500).
        # With 5 dests, max sources/batch is floor(2500/5) - 1 = 499; capped at 10.
        mock_query.return_value = [[0.0] * 5]
        locations = {f's{i}': [0.0, 0.0] for i in range(25)}
        locations.update({f'd{j}': [1.0, 1.0] for j in range(5)})
        build_distance_matrix(
            locations=locations,
            source_ids=[f's{i}' for i in range(25)],
            dest_ids=[f'd{j}' for j in range(5)],
            matrix_url='http://ors:8080/ors/v2/matrix/driving-car',
        )
        # With 25 sources and batch <= 10, query_matrix is called at least 3 times.
        assert mock_query.call_count >= 3
        # MATRIX_CELL_LIMIT is exposed for callers that want to compute their own batches.
        assert MATRIX_CELL_LIMIT == 2500

    @patch('python.utils.driving_distance_matrix.query_directions')
    @patch('python.utils.driving_distance_matrix.query_matrix')
    def test_retries_individual_sources_on_batch_failure(self, mock_matrix, mock_directions):
        mock_matrix.side_effect = OrsMatrixError('batch failed')
        mock_directions.return_value = 12345.0
        locations = {'a': [-84.0, 33.9], 'b': [-84.1, 34.0]}
        result = build_distance_matrix(
            locations=locations,
            source_ids=['a'],
            dest_ids=['b'],
            matrix_url='http://ors:8080/ors/v2/matrix/driving-car',
        )
        # query_directions should have been called for the failing source x each dest.
        assert mock_directions.called
        assert (result['distance_m'] == 12345.0).any()


class TestResumeFromPartialOutput:
    '''Partial-CSV resume: skip pairs already populated, do not silently exit.

    Fixes the upstream geolib bug where an existing partial output caused
    get_all_distances to return after printing missing origins (no work done).
    '''

    def test_returns_existing_pairs_unchanged_and_remaining_pairs_to_fetch(self, tmp_path):
        existing_csv = tmp_path / 'partial.csv'
        pd.DataFrame({
            'id_orig': ['a', 'a'],
            'id_dest': ['x', 'y'],
            'distance_m': [100.0, 200.0],
        }).to_csv(existing_csv, index=False)

        existing_df, remaining_pairs = resume_from_partial_output(
            existing_csv,
            source_ids=['a', 'b'],
            dest_ids=['x', 'y'],
        )
        assert len(existing_df) == 2
        # b x {x, y} are the only pairs not yet present.
        assert set(remaining_pairs) == {('b', 'x'), ('b', 'y')}

    def test_returns_empty_existing_when_file_absent(self, tmp_path):
        existing_df, remaining_pairs = resume_from_partial_output(
            tmp_path / 'absent.csv',
            source_ids=['a'],
            dest_ids=['x'],
        )
        assert existing_df.empty
        assert set(remaining_pairs) == {('a', 'x')}
