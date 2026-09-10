'''Tests for python/scripts/generate_driving_distances_cli.py.'''
import os
import urllib.error
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from python.scripts.generate_driving_distances_cli import (
    build_arg_parser,
    derive_origins_and_destinations,
    main,
    write_output_csv,
)
from python.solver.constants import (
    POT_LOC_LAT_LON,
    POT_LOC_LOCATION,
    TIGER20_GEOID20,
    TIGER20_INTPTLAT20,
    TIGER20_INTPTLON20,
)


class TestArgParser:
    '''CLI argument parsing.'''

    def test_requires_location_config(self):
        parser = build_arg_parser()
        with pytest.raises(SystemExit):
            parser.parse_args([])

    def test_parses_location_config(self):
        parser = build_arg_parser()
        args = parser.parse_args(['-l', 'Gwinnett_GA/cfg.yaml'])
        assert args.location_config == 'Gwinnett_GA/cfg.yaml'

    def test_default_logdir(self):
        parser = build_arg_parser()
        args = parser.parse_args(['-l', 'x.yaml'])
        assert args.logdir == './logs'

    def test_testing_defaults_to_false(self):
        parser = build_arg_parser()
        args = parser.parse_args(['-l', 'x.yaml'])
        assert args.testing is False

    def test_explicit_testing_flag(self):
        parser = build_arg_parser()
        args = parser.parse_args(['--testing', '-l', 'x.yaml'])
        assert args.testing is True

    def test_server_and_logdir_overrides(self):
        parser = build_arg_parser()
        args = parser.parse_args([
            '-l', 'x.yaml',
            '--server', 'http://foo:8080/ors/v2/matrix/driving-car',
            '--logdir', '/tmp/mylogs',
        ])
        assert args.server == 'http://foo:8080/ors/v2/matrix/driving-car'
        assert args.logdir == '/tmp/mylogs'


class TestWriteOutputCsv:
    '''Output CSV has exactly id_orig,id_dest,distance_m (no provenance col).'''

    def test_writes_only_three_columns_in_order(self, tmp_path):
        df = pd.DataFrame({
            'id_orig': ['a', 'b'],
            'id_dest': ['x', 'y'],
            'distance_m': [10.0, 20.0],
            'source': ['driving', 'driving'],   # Provenance column to be stripped.
        })
        out_path = tmp_path / 'out.csv'
        write_output_csv(df, str(out_path))
        written = pd.read_csv(out_path)
        assert list(written.columns) == ['id_orig', 'id_dest', 'distance_m']


class TestDeriveOriginsAndDestinations:
    '''Reuses model_data.py helpers to build origin/dest sets from config.'''

    @patch('python.scripts.generate_driving_distances_cli.load_potential_locations_csv')
    @patch('python.scripts.generate_driving_distances_cli.get_blocks_gdf')
    def test_handles_combined_lat_lon_column(self, mock_blocks, mock_pots):
        '''Split a single "Lat, Lon" column into [lon, lat] values.'''
        mock_blocks.return_value = pd.DataFrame({
            TIGER20_GEOID20: ['111'],
            TIGER20_INTPTLAT20: ['32.7'],
            TIGER20_INTPTLON20: ['-97.3'],
        })
        mock_pots.return_value = pd.DataFrame({
            POT_LOC_LOCATION: ['pollA', 'pollB'],
            POT_LOC_LAT_LON: ['32.707497 , -97.252456', '32.711546, -97.189768'],
        })

        config = MagicMock(location='Tarrant_County_TX', census_year='2020')
        locations, source_ids, dest_ids = derive_origins_and_destinations(config)
        assert set(source_ids) == {'111'}
        assert set(dest_ids) == {'pollA', 'pollB'}
        assert locations['111'] == [-97.3, 32.7]
        # ``[lon, lat]`` order — parser puts lon first.
        assert locations['pollA'] == [-97.252456, 32.707497]
        assert locations['pollB'] == [-97.189768, 32.711546]


class TestMain:
    '''Smoke-test the happy path end to end, everything mocked.'''

    @patch('python.scripts.generate_driving_distances_cli._assert_ors_reachable')
    @patch('python.scripts.generate_driving_distances_cli.build_distance_matrix')
    @patch('python.scripts.generate_driving_distances_cli.derive_origins_and_destinations')
    @patch('python.scripts.generate_driving_distances_cli.PollingModelConfig')
    def test_writes_csv_at_expected_path(self, mock_cfg_cls, mock_derive, mock_build, unused_mock_reach, tmp_path):
        del unused_mock_reach
        mock_cfg_cls.load_config.return_value = MagicMock(
            location='testing', census_year='2020',
            config_file_path=str(tmp_path / 'cfg.yaml'),
        )
        mock_derive.return_value = (
            {'a': [-84.0, 33.9], 'x': [-84.1, 34.0]},
            ['a'],
            ['x'],
        )
        mock_build.return_value = pd.DataFrame({
            'id_orig': ['a'], 'id_dest': ['x'], 'distance_m': [12345.0],
        })

        driving_dir = tmp_path / 'datasets' / 'driving' / 'testing'
        logdir = tmp_path / 'logs'
        os.makedirs(driving_dir, exist_ok=True)
        os.makedirs(logdir, exist_ok=True)

        # The CLI writes to datasets/driving/<Loc>/<Loc>_driving_distances.csv —
        # patch the output-path builder so the test stays inside tmp_path.
        with patch(
            'python.scripts.generate_driving_distances_cli.build_output_csv_path',
            return_value=str(driving_dir / 'testing_driving_distances.csv'),
        ):
            main([
                '--testing',
                '-l', str(tmp_path / 'cfg.yaml'),
                '--logdir', str(logdir),
            ])

        written = pd.read_csv(driving_dir / 'testing_driving_distances.csv')
        assert list(written.columns) == ['id_orig', 'id_dest', 'distance_m']
        assert written.iloc[0]['distance_m'] == 12345.0


class TestResumeBehavior:
    '''Resume/partial-fetch mechanics: only the remaining pairs reach build_distance_matrix.'''

    @patch('python.scripts.generate_driving_distances_cli._assert_ors_reachable')
    @patch('python.scripts.generate_driving_distances_cli.build_distance_matrix')
    @patch('python.scripts.generate_driving_distances_cli.derive_origins_and_destinations')
    @patch('python.scripts.generate_driving_distances_cli.PollingModelConfig')
    def test_resume_skips_pairs_already_in_output(
        self, mock_cfg_cls, mock_derive, mock_build, unused_mock_reach, tmp_path,
    ):
        '''When the output CSV exists, only the remaining pairs are sent to build_distance_matrix.'''
        del unused_mock_reach
        mock_cfg_cls.load_config.return_value = MagicMock(
            location='testing', census_year='2020',
            config_file_path=str(tmp_path / 'cfg.yaml'),
        )
        mock_derive.return_value = (
            {'a': [-84.0, 33.9], 'b': [-84.0, 33.91], 'x': [-84.1, 34.0]},
            ['a', 'b'],
            ['x'],
        )
        mock_build.return_value = pd.DataFrame({
            'id_orig': ['b'], 'id_dest': ['x'], 'distance_m': [777.0],
        })

        driving_dir = tmp_path / 'datasets' / 'driving' / 'testing'
        os.makedirs(driving_dir, exist_ok=True)
        expected_output = driving_dir / 'testing_driving_distances.csv'
        # Pre-existing partial output: (a, x) already done.
        pd.DataFrame({
            'id_orig': ['a'], 'id_dest': ['x'], 'distance_m': [100.0],
        }).to_csv(expected_output, index=False)

        logdir = tmp_path / 'logs'
        os.makedirs(logdir, exist_ok=True)
        with patch(
            'python.scripts.generate_driving_distances_cli.build_output_csv_path',
            return_value=str(expected_output),
        ):
            main([
                '--testing',
                '-l', str(tmp_path / 'cfg.yaml'),
                '--logdir', str(logdir),
            ])

        # build_distance_matrix should have been called with ONLY the remaining source/dest.
        build_call_kwargs = mock_build.call_args.kwargs
        assert build_call_kwargs['source_ids'] == ['b']
        assert build_call_kwargs['dest_ids'] == ['x']

        # Combined output: both (a, x) and (b, x) present, no duplicates.
        written = pd.read_csv(expected_output)
        assert set(zip(written['id_orig'], written['id_dest'])) == {('a', 'x'), ('b', 'x')}

    @patch('python.scripts.generate_driving_distances_cli._assert_ors_reachable')
    @patch('python.scripts.generate_driving_distances_cli.build_distance_matrix')
    @patch('python.scripts.generate_driving_distances_cli.derive_origins_and_destinations')
    @patch('python.scripts.generate_driving_distances_cli.PollingModelConfig')
    def test_resume_short_circuits_when_nothing_remains(
        self, mock_cfg_cls, mock_derive, mock_build, unused_mock_reach, tmp_path,
    ):
        '''When every requested pair is already in the output CSV, build_distance_matrix is never called.'''
        del unused_mock_reach
        mock_cfg_cls.load_config.return_value = MagicMock(
            location='testing', census_year='2020',
            config_file_path=str(tmp_path / 'cfg.yaml'),
        )
        mock_derive.return_value = (
            {'a': [-84.0, 33.9], 'x': [-84.1, 34.0]},
            ['a'],
            ['x'],
        )

        driving_dir = tmp_path / 'datasets' / 'driving' / 'testing'
        os.makedirs(driving_dir, exist_ok=True)
        expected_output = driving_dir / 'testing_driving_distances.csv'
        pd.DataFrame({
            'id_orig': ['a'], 'id_dest': ['x'], 'distance_m': [100.0],
        }).to_csv(expected_output, index=False)

        logdir = tmp_path / 'logs'
        os.makedirs(logdir, exist_ok=True)
        with patch(
            'python.scripts.generate_driving_distances_cli.build_output_csv_path',
            return_value=str(expected_output),
        ):
            rc = main([
                '--testing',
                '-l', str(tmp_path / 'cfg.yaml'),
                '--logdir', str(logdir),
            ])

        assert rc == 0
        assert not mock_build.called


class TestUnroutedOriginReporting:
    '''_report_unrouted_origins fires correctly and the run exits non-zero, partial data kept.'''

    @patch('python.scripts.generate_driving_distances_cli._assert_ors_reachable')
    @patch('python.scripts.generate_driving_distances_cli.build_distance_matrix')
    @patch('python.scripts.generate_driving_distances_cli.derive_origins_and_destinations')
    @patch('python.scripts.generate_driving_distances_cli.PollingModelConfig')
    def test_write_path_exits_nonzero_but_still_writes_partial_csv(
        self, mock_cfg_cls, mock_derive, mock_build, unused_mock_reach, tmp_path, capsys,
    ):
        '''An unrouted origin fails the run loudly, but completed work is kept:
        the partial CSV is written first, then the run exits non-zero and
        enumerates exactly which origins are missing, with id and lat/lon.'''

        del unused_mock_reach
        #configure mocks: config, an origin that never gets routed, one good pair
        mock_cfg_cls.load_config.return_value = MagicMock(
            location='testing', census_year='2020',
            config_file_path=str(tmp_path / 'cfg.yaml'),
        )
        mock_derive.return_value = (
            {
                'block_ok': [-84.0, 33.9],
                'block_bad': [-84.05, 33.91],
                'poll_x': [-84.1, 34.0],
            },
            ['block_ok', 'block_bad'],
            ['poll_x'],
        )
        mock_build.return_value = pd.DataFrame({
            'id_orig': ['block_ok'], 'id_dest': ['poll_x'], 'distance_m': [12345.0],
        })

        #set up output and log paths under tmp_path
        driving_dir = tmp_path / 'datasets' / 'driving' / 'testing'
        logdir = tmp_path / 'logs'
        os.makedirs(driving_dir, exist_ok=True)
        os.makedirs(logdir, exist_ok=True)
        expected_output = driving_dir / 'testing_driving_distances.csv'

        #run the CLI
        with patch(
            'python.scripts.generate_driving_distances_cli.build_output_csv_path',
            return_value=str(expected_output),
        ):
            rc = main([
                '--testing',
                '-l', str(tmp_path / 'cfg.yaml'),
                '--logdir', str(logdir),
            ])

        #verify: failure exit code, partial CSV kept, missing origin named in the message
        assert rc == 1
        # The partial CSV keeps the successfully routed rows.
        written = pd.read_csv(expected_output)
        assert set(written['id_orig']) == {'block_ok'}
        out = capsys.readouterr().out
        # The failure message names the CSV the missing rows are absent from.
        assert f'no rows in {expected_output}' in out
        assert 'block_bad' in out
        assert '33.91' in out
        assert '-84.05' in out

    @patch('python.scripts.generate_driving_distances_cli._assert_ors_reachable')
    @patch('python.scripts.generate_driving_distances_cli.build_distance_matrix')
    @patch('python.scripts.generate_driving_distances_cli.derive_origins_and_destinations')
    @patch('python.scripts.generate_driving_distances_cli.PollingModelConfig')
    def test_short_circuit_exits_nonzero_on_blank_distance_row(
        self, mock_cfg_cls, mock_derive, mock_build, unused_mock_reach, tmp_path, capsys,
    ):
        '''A blank distance_m must fail
        '''
        del unused_mock_reach
        mock_cfg_cls.load_config.return_value = MagicMock(
            location='testing', census_year='2020',
            config_file_path=str(tmp_path / 'cfg.yaml'),
        )
        mock_derive.return_value = (
            {
                'block_ok': [-84.0, 33.9],
                'block_blank': [-84.05, 33.91],
                'poll_x': [-84.1, 34.0],
            },
            ['block_ok', 'block_blank'],
            ['poll_x'],
        )

        driving_dir = tmp_path / 'datasets' / 'driving' / 'testing'
        os.makedirs(driving_dir, exist_ok=True)
        expected_output = driving_dir / 'testing_driving_distances.csv'
        # Every requested pair is present, but one row has a blank distance_m
        # (as a human patching the file might leave it).
        pd.DataFrame({
            'id_orig': ['block_ok', 'block_blank'],
            'id_dest': ['poll_x', 'poll_x'],
            'distance_m': [100.0, None],
        }).to_csv(expected_output, index=False)

        logdir = tmp_path / 'logs'
        os.makedirs(logdir, exist_ok=True)
        with patch(
            'python.scripts.generate_driving_distances_cli.build_output_csv_path',
            return_value=str(expected_output),
        ):
            rc = main([
                '--testing',
                '-l', str(tmp_path / 'cfg.yaml'),
                '--logdir', str(logdir),
            ])

        assert rc == 1
        assert not mock_build.called   # no pairs remained; nothing was fetched
        out = capsys.readouterr().out
        assert 'blank distance_m' in out
        assert 'block_blank' in out
        assert 'will NOT fetch' in out


class TestStateResolution:
    '''Resolving state: derived from config.location, or hardcoded via --testing.'''

    @patch('python.scripts.generate_driving_distances_cli._assert_ors_reachable')
    @patch('python.scripts.generate_driving_distances_cli.build_distance_matrix')
    @patch('python.scripts.generate_driving_distances_cli.derive_origins_and_destinations')
    @patch('python.scripts.generate_driving_distances_cli.PollingModelConfig')
    def test_derives_state_from_config_location_when_no_flag(
            self, mock_cfg_cls, mock_derive, mock_build, unused_mock_reach, tmp_path):
        '''No --testing, config.location='Gwinnett_County_GA' -> state resolves to georgia.

        The script doesn't expose the derived state via a return value, but
        if derivation fails the call exits non-zero. Asserting a clean run
        confirms the happy-path derivation.
        '''
        del unused_mock_reach
        mock_cfg_cls.load_config.return_value = MagicMock(
            location='Gwinnett_County_GA', census_year='2020',
            config_file_path=str(tmp_path / 'cfg.yaml'),
        )
        mock_derive.return_value = (
            {'a': [-84.0, 33.9], 'x': [-84.1, 34.0]},
            ['a'],
            ['x'],
        )
        mock_build.return_value = pd.DataFrame({
            'id_orig': ['a'], 'id_dest': ['x'], 'distance_m': [12345.0],
        })
        driving_dir = tmp_path / 'datasets' / 'driving' / 'Gwinnett_County_GA'
        logdir = tmp_path / 'logs'
        os.makedirs(driving_dir, exist_ok=True)
        os.makedirs(logdir, exist_ok=True)
        with patch(
            'python.scripts.generate_driving_distances_cli.build_output_csv_path',
            return_value=str(driving_dir / 'Gwinnett_County_GA_driving_distances.csv'),
        ):
            rc = main([
                '-l', str(tmp_path / 'cfg.yaml'),
                '--logdir', str(logdir),
            ])
        assert rc == 0

    @patch('python.scripts.generate_driving_distances_cli._assert_ors_reachable')
    @patch('python.scripts.generate_driving_distances_cli.build_distance_matrix')
    @patch('python.scripts.generate_driving_distances_cli.derive_origins_and_destinations')
    @patch('python.scripts.generate_driving_distances_cli.PollingModelConfig')
    def test_testing_flag_succeeds_despite_nonderivable_location(
            self, mock_cfg_cls, mock_derive, mock_build, unused_mock_reach, tmp_path):
        '''--testing present, config.location='testing' (no derivable suffix) -> succeeds.

        Proves --testing bypasses derivation entirely: the same location fails
        without the flag (see test_errors_when_neither_flag_nor_derivable_location)
        but succeeds here.
        '''
        del unused_mock_reach
        mock_cfg_cls.load_config.return_value = MagicMock(
            location='testing', census_year='2020',
            config_file_path=str(tmp_path / 'cfg.yaml'),
        )
        mock_derive.return_value = (
            {'a': [-84.0, 33.9], 'x': [-84.1, 34.0]},
            ['a'],
            ['x'],
        )
        mock_build.return_value = pd.DataFrame({
            'id_orig': ['a'], 'id_dest': ['x'], 'distance_m': [12345.0],
        })
        driving_dir = tmp_path / 'datasets' / 'driving' / 'testing'
        logdir = tmp_path / 'logs'
        os.makedirs(driving_dir, exist_ok=True)
        os.makedirs(logdir, exist_ok=True)
        with patch(
            'python.scripts.generate_driving_distances_cli.build_output_csv_path',
            return_value=str(driving_dir / 'testing_driving_distances.csv'),
        ):
            rc = main([
                '--testing',
                '-l', str(tmp_path / 'cfg.yaml'),
                '--logdir', str(logdir),
            ])
        assert rc == 0

    @patch('python.scripts.generate_driving_distances_cli._assert_ors_reachable')
    @patch('python.scripts.generate_driving_distances_cli.PollingModelConfig')
    def test_errors_when_neither_flag_nor_derivable_location(
            self, mock_cfg_cls, unused_mock_reach):
        '''No --testing, config.location='testing' -> exit 2 with actionable error.'''
        del unused_mock_reach
        mock_cfg_cls.load_config.return_value = MagicMock(
            location='testing', census_year='2020',
            config_file_path='/tmp/cfg.yaml',
        )
        with pytest.raises(SystemExit) as exc_info:
            main(['-l', '/tmp/cfg.yaml'])
        assert exc_info.value.code == 2


class TestInContainerHealthCheck:
    '''Tests for the in-container ORS reachability check.'''

    @patch('python.scripts.generate_driving_distances_cli.urllib.request.urlopen',
           side_effect=urllib.error.URLError('connection refused'))
    def test_exits_when_ors_unreachable(self, unused_mock_urlopen):
        '''When ORS is unreachable, main must exit with code 1 from _assert_ors_reachable.

        Asserting the exact exit code 1 (not just != 0) verifies the exit came from
        the reachability probe, not from a later PollingModelConfig.load_config failure.
        '''
        del unused_mock_urlopen
        with pytest.raises(SystemExit) as exc_info:
            main(['-l', '/nonexistent.yaml'])
        assert exc_info.value.code == 1
