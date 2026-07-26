'''Tests for python/utils/driving_distance_matrix.py.'''
import io
from unittest.mock import patch

import numpy as np
import pandas as pd
import pytest

from python.utils.driving_distance_matrix import (
    MATRIX_CELL_LIMIT,
    MAX_SOURCES_PER_BATCH,
    _LEVEL_DEFAULT,
    _LEVEL_V,
    _LEVEL_VV,
    _emit,
    _reject_negative_distances,
    build_distance_matrix,
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
            log_fh=io.StringIO(),
            verbosity=0,
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
            log_fh=io.StringIO(),
            verbosity=0,
        )
        # With 25 sources and batch <= 10, query_matrix is called at least 3 times.
        assert mock_query.call_count >= 3
        for call in mock_query.call_args_list:
            sources = call.args[1] if len(call.args) > 1 else call.kwargs.get('sources')
            assert len(sources) <= MAX_SOURCES_PER_BATCH
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
            log_fh=io.StringIO(),
            verbosity=0,
        )
        # query_directions should have been called for the failing source x each dest.
        assert mock_directions.called
        assert (result['distance_m'] == 12345.0).any()
        # The directions URL must be derived from the matrix URL via the project helper.
        expected_directions_url = 'http://ors:8080/ors/v2/directions/driving-car'
        for call in mock_directions.call_args_list:
            assert call.args[2] == expected_directions_url


class TestUnroutableOriginsAreDropped:
    '''An unroutable origin yields no rows — never a fabricated estimate (#325).'''

    @patch('python.utils.driving_distance_matrix.query_matrix')
    def test_unroutable_origin_rows_are_dropped_not_fabricated(self, mock_query):
        '''Even with a routable origin ~111 m away, no distance is invented.

        The haversine snap fallback was removed per #325: a fabricated
        distance is indistinguishable from a real route in the output.
        Callers detect dropped origins by comparing requested source_ids
        against the returned id_orig values and must fail loud.
        '''
        # s1 is ~111 m north of s0 — the old snap path would have borrowed
        # s0's route and fabricated a row for s1.
        mock_query.return_value = [[100.0], [np.nan]]
        log_fh = io.StringIO()
        df = build_distance_matrix(
            locations={
                's0': [-84.0000, 33.9500],
                's1': [-84.0000, 33.9510],
                'd':  [-84.1000, 34.0000],
            },
            source_ids=['s0', 's1'],
            dest_ids=['d'],
            matrix_url='http://ors:8082/ors/v2/matrix/driving-car',
            log_fh=log_fh, verbosity=0,
        )
        assert set(df['id_orig']) == {'s0'}
        assert df['distance_m'].notna().all()
        assert 'snapped' not in log_fh.getvalue()


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

    def test_numeric_geoids_already_present_are_recognized(self, tmp_path):
        '''Numeric-looking GEOIDs must match str source_ids so resume skips them.

        Regression for #305: pd.read_csv infers id_orig as int64 for numeric
        census-block GEOIDs, so the present-pair check never matched the str
        source_ids built by the CLI. Every pair looked "remaining" and got
        re-fetched, then survived drop_duplicates as a duplicate row (one int
        key from the old file, one str key freshly fetched).
        '''
        existing_csv = tmp_path / 'partial.csv'
        pd.DataFrame({
            'id_orig': ['540610120004019', '540610120004019'],
            'id_dest': ['University High School', 'Triune-Halleck VFD'],
            'distance_m': [100.0, 200.0],
        }).to_csv(existing_csv, index=False)

        existing_df, remaining_pairs = resume_from_partial_output(
            existing_csv,
            source_ids=['540610120004019'],
            dest_ids=['University High School', 'Triune-Halleck VFD'],
        )
        # The CSV already covers every requested pair, so nothing remains.
        assert remaining_pairs == []
        # id_orig must load as str (not int64) so the CLI's later concat +
        # drop_duplicates keys match the freshly-fetched str ids.
        assert existing_df['id_orig'].dtype == object
        assert existing_df['id_orig'].iloc[0] == '540610120004019'


class TestEmitHelper:
    '''_emit writes to log_fh always; to stdout only when level <= verbosity.'''

    def test_level_default_always_visible_in_log_and_screen_at_verbosity_0(self, capsys):
        log_fh = io.StringIO()
        _emit('hello', _LEVEL_DEFAULT, log_fh, 0)
        assert log_fh.getvalue() == 'hello\n'
        assert capsys.readouterr().out == 'hello\n'

    def test_level_v_hidden_from_screen_at_verbosity_0_but_in_log(self, capsys):
        log_fh = io.StringIO()
        _emit('per-batch', _LEVEL_V, log_fh, 0)
        assert log_fh.getvalue() == 'per-batch\n'
        assert capsys.readouterr().out == ''

    def test_level_v_appears_on_screen_at_verbosity_1(self, capsys):
        log_fh = io.StringIO()
        _emit('per-batch', _LEVEL_V, log_fh, 1)
        assert log_fh.getvalue() == 'per-batch\n'
        assert capsys.readouterr().out == 'per-batch\n'

    def test_level_vv_hidden_from_screen_at_verbosity_1(self, capsys):
        log_fh = io.StringIO()
        _emit('retry', _LEVEL_VV, log_fh, 1)
        assert log_fh.getvalue() == 'retry\n'
        assert capsys.readouterr().out == ''

    def test_level_vv_appears_on_screen_at_verbosity_2(self, capsys):
        log_fh = io.StringIO()
        _emit('retry', _LEVEL_VV, log_fh, 2)
        assert log_fh.getvalue() == 'retry\n'
        assert capsys.readouterr().out == 'retry\n'

    def test_level_constants_match_expected_integers(self):
        assert (_LEVEL_DEFAULT, _LEVEL_V, _LEVEL_VV) == (0, 1, 2)


class TestVerbosityGating:
    '''build_distance_matrix writes per-batch + snap + retry events at the right levels.'''

    @patch('python.utils.driving_distance_matrix.query_matrix')
    def test_per_batch_in_log_but_not_screen_at_default(self, mock_query, capsys):
        mock_query.return_value = [[0.0]]
        log_fh = io.StringIO()
        build_distance_matrix(
            locations={'a': [-84.0, 33.9], 'd': [-84.1, 34.0]},
            source_ids=['a'], dest_ids=['d'],
            matrix_url='http://ors:8082/ors/v2/matrix/driving-car',
            log_fh=log_fh, verbosity=0,
        )
        # batch-progress format is '{done}/{total}: {elapsed:.2f}s'
        assert '1/1:' in log_fh.getvalue()
        assert '1/1:' not in capsys.readouterr().out

    @patch('python.utils.driving_distance_matrix.query_matrix')
    def test_per_batch_appears_on_screen_at_v(self, mock_query, capsys):
        mock_query.return_value = [[0.0]]
        log_fh = io.StringIO()
        build_distance_matrix(
            locations={'a': [-84.0, 33.9], 'd': [-84.1, 34.0]},
            source_ids=['a'], dest_ids=['d'],
            matrix_url='http://ors:8082/ors/v2/matrix/driving-car',
            log_fh=log_fh, verbosity=1,
        )
        assert '1/1:' in log_fh.getvalue()
        assert '1/1:' in capsys.readouterr().out

    @patch('python.utils.driving_distance_matrix.query_directions')
    @patch('python.utils.driving_distance_matrix.query_matrix')
    def test_retry_hidden_at_v_visible_at_vv(self, mock_matrix, mock_directions, capsys):
        mock_matrix.side_effect = OrsMatrixError('boom')
        mock_directions.return_value = 100.0

        log_fh = io.StringIO()
        build_distance_matrix(
            locations={'a': [-84.0, 33.9], 'b': [-84.1, 34.0]},
            source_ids=['a'], dest_ids=['b'],
            matrix_url='http://ors:8082/ors/v2/matrix/driving-car',
            log_fh=log_fh, verbosity=1,
        )
        assert 'retrying source a' in log_fh.getvalue()
        assert 'retrying source a' not in capsys.readouterr().out

        log_fh = io.StringIO()
        build_distance_matrix(
            locations={'a': [-84.0, 33.9], 'b': [-84.1, 34.0]},
            source_ids=['a'], dest_ids=['b'],
            matrix_url='http://ors:8082/ors/v2/matrix/driving-car',
            log_fh=log_fh, verbosity=2,
        )
        assert 'retrying source a' in capsys.readouterr().out

class TestRejectNegativeDistances:
    '''A negative distance_m fails loudly at generation (#294); 0 and NaN pass.'''

    def test_negative_distance_raises_value_error(self):
        df = pd.DataFrame({
            'id_orig': ['a', 'b'],
            'id_dest': ['x', 'x'],
            'distance_m': [100.0, -1.0],
        })
        with pytest.raises(ValueError, match='negative'):
            _reject_negative_distances(df)

    def test_zero_and_nan_are_left_untouched(self):
        df = pd.DataFrame({
            'id_orig': ['a', 'b'],
            'id_dest': ['x', 'x'],
            'distance_m': [0.0, np.nan],
        })
        _reject_negative_distances(df)   # Must not raise.
        assert df.loc[0, 'distance_m'] == 0.0
        assert pd.isnull(df.loc[1, 'distance_m'])


class TestBuildMatrixNegativeHandling:
    '''A negative matrix cell from the routing backend fails the whole run.'''

    @patch('python.utils.driving_distance_matrix.query_matrix')
    def test_negative_distance_from_backend_raises(self, mock_query):
        mock_query.return_value = [[100.0], [-1.0]]
        with pytest.raises(ValueError, match='negative'):
            build_distance_matrix(
                locations={
                    's0': [-84.0000, 33.9500],
                    's1': [-84.0000, 33.9510],  # ~111m north of s0
                    'd':  [-84.1000, 34.0000],
                },
                source_ids=['s0', 's1'],
                dest_ids=['d'],
                matrix_url='http://ors:8082/ors/v2/matrix/driving-car',
                log_fh=io.StringIO(),
                verbosity=0,
            )
