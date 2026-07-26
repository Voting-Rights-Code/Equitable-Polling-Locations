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

    def test_state_defaults_to_none(self):
        parser = build_arg_parser()
        args = parser.parse_args(['-l', 'x.yaml'])
        assert args.state is None

    def test_explicit_state_flag(self):
        parser = build_arg_parser()
        args = parser.parse_args(['--state', 'georgia', '-l', 'x.yaml'])
        assert args.state == 'georgia'

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
    def test_returns_locations_dict_and_id_lists(self, mock_blocks, mock_pots):
        # Mock the block centroid GeoDataFrame.
        mock_blocks.return_value = pd.DataFrame({
            'GEOID20': ['111', '222'],
            'INTPTLAT20': ['33.9', '34.0'],
            'INTPTLON20': ['-84.0', '-84.1'],
        })
        mock_pots.return_value = pd.DataFrame({
            'Location': ['pollA', 'pollB'],
            'Latitude': [33.95, 34.05],
            'Longitude': [-84.05, -84.15],
        })

        config = MagicMock(location='Gwinnett_GA', census_year='2020')
        locations, source_ids, dest_ids = derive_origins_and_destinations(config)
        assert set(source_ids) == {'111', '222'}
        assert set(dest_ids) == {'pollA', 'pollB'}
        assert locations['111'] == [-84.0, 33.9]      # ``[lon, lat]`` order
        assert locations['pollA'] == [-84.05, 33.95]

    @patch('python.scripts.generate_driving_distances_cli.load_potential_locations_csv')
    @patch('python.scripts.generate_driving_distances_cli.get_blocks_gdf')
    def test_handles_combined_lat_lon_column(self, mock_blocks, mock_pots):
        '''Tarrant_County_TX-style CSV uses a single "Lat, Long" column with "lat , lon" values.'''
        mock_blocks.return_value = pd.DataFrame({
            'GEOID20': ['111'],
            'INTPTLAT20': ['32.7'],
            'INTPTLON20': ['-97.3'],
        })
        mock_pots.return_value = pd.DataFrame({
            'Location': ['pollA', 'pollB'],
            'Lat, Long': ['32.707497 , -97.252456', '32.711546,-97.189768'],  # both spacings
        })

        config = MagicMock(location='Tarrant_County_TX', census_year='2020')
        locations, source_ids, dest_ids = derive_origins_and_destinations(config)
        assert set(source_ids) == {'111'}
        assert set(dest_ids) == {'pollA', 'pollB'}
        # ``[lon, lat]`` order — parser puts lon first.
        assert locations['pollA'] == [-97.252456, 32.707497]
        assert locations['pollB'] == [-97.189768, 32.711546]

    @patch('python.scripts.generate_driving_distances_cli.load_potential_locations_csv')
    @patch('python.scripts.generate_driving_distances_cli.get_blocks_gdf')
    def test_raises_when_no_coord_columns(self, mock_blocks, mock_pots):
        '''Neither separate Latitude/Longitude nor combined column → clear ValueError.'''
        mock_blocks.return_value = pd.DataFrame({
            'GEOID20': ['111'],
            'INTPTLAT20': ['32.7'],
            'INTPTLON20': ['-97.3'],
        })
        mock_pots.return_value = pd.DataFrame({
            'Location': ['pollA'],
            'Address': ['somewhere'],
            # no coord columns at all
        })

        config = MagicMock(location='Tarrant_County_TX', census_year='2020')
        with pytest.raises(ValueError, match='Latitude/Longitude'):
            derive_origins_and_destinations(config)


class TestMain:
    '''Smoke-test the end-to-end flow with everything mocked.'''

    @patch('python.scripts.generate_driving_distances_cli._assert_ors_reachable')
    @patch('python.scripts.generate_driving_distances_cli.build_distance_matrix')
    @patch('python.scripts.generate_driving_distances_cli.derive_origins_and_destinations')
    @patch('python.scripts.generate_driving_distances_cli.PollingModelConfig')
    def test_writes_csv_at_expected_path(self, mock_cfg_cls, mock_derive, mock_build, unused_mock_reach, tmp_path):
        del unused_mock_reach
        mock_cfg_cls.load_config.return_value = MagicMock(
            location='Gwinnett_GA', census_year='2020',
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

        driving_dir = tmp_path / 'datasets' / 'driving' / 'Gwinnett_GA'
        logdir = tmp_path / 'logs'
        os.makedirs(driving_dir, exist_ok=True)
        os.makedirs(logdir, exist_ok=True)

        # The CLI writes to datasets/driving/<Loc>/<Loc>_driving_distances.csv —
        # patch the output-path builder so the test stays inside tmp_path.
        with patch(
            'python.scripts.generate_driving_distances_cli.build_output_csv_path',
            return_value=str(driving_dir / 'Gwinnett_GA_driving_distances.csv'),
        ):
            main([
                '--state', 'georgia',
                '-l', str(tmp_path / 'cfg.yaml'),
                '--logdir', str(logdir),
            ])

        written = pd.read_csv(driving_dir / 'Gwinnett_GA_driving_distances.csv')
        assert list(written.columns) == ['id_orig', 'id_dest', 'distance_m']
        assert written.iloc[0]['distance_m'] == 12345.0

    @patch('python.scripts.generate_driving_distances_cli._assert_ors_reachable')
    @patch('python.scripts.generate_driving_distances_cli.build_distance_matrix')
    @patch('python.scripts.generate_driving_distances_cli.derive_origins_and_destinations')
    @patch('python.scripts.generate_driving_distances_cli.PollingModelConfig')
    def test_check_bad_locations_exits_nonzero_and_lists_unrouted_origins(
        self, mock_cfg_cls, mock_derive, mock_build, unused_mock_reach, tmp_path, capsys,
    ):
        '''--check-bad-locations writes no CSV; unrouted origins -> exit 1 + id/lat/lon.'''
        del unused_mock_reach
        mock_cfg_cls.load_config.return_value = MagicMock(
            location='Gwinnett_GA', census_year='2020',
            config_file_path=str(tmp_path / 'cfg.yaml'),
        )
        mock_derive.return_value = (
            {
                'block_ok': [-84.0, 33.9],
                'block_bad': [-84.05, 33.91],
                'poll_x': [-84.1, 34.0],
            },
            ['block_ok', 'block_bad'],   # block_bad absent from build result -> unrouted
            ['poll_x'],
        )
        mock_build.return_value = pd.DataFrame({
            'id_orig': ['block_ok'], 'id_dest': ['poll_x'], 'distance_m': [12345.0],
        })

        driving_dir = tmp_path / 'datasets' / 'driving' / 'Gwinnett_GA'
        logdir = tmp_path / 'logs'
        os.makedirs(logdir, exist_ok=True)
        # build_output_csv_path is NEVER reached in this code path, but patch it
        # anyway so a regression that wrongly fell through would still not touch
        # the real filesystem.
        expected_output = driving_dir / 'Gwinnett_GA_driving_distances.csv'

        with patch(
            'python.scripts.generate_driving_distances_cli.build_output_csv_path',
            return_value=str(expected_output),
        ):
            rc = main([
                '--state', 'georgia',
                '-l', str(tmp_path / 'cfg.yaml'),
                '--logdir', str(logdir),
                '--check-bad-locations',
            ])

        assert rc == 1
        assert not driving_dir.exists() or not expected_output.exists()
        out = capsys.readouterr().out
        assert 'block_bad' in out
        assert '33.91' in out       # latitude of the unrouted origin
        assert '-84.05' in out      # longitude of the unrouted origin

    @patch('python.scripts.generate_driving_distances_cli._assert_ors_reachable')
    @patch('python.scripts.generate_driving_distances_cli.build_distance_matrix')
    @patch('python.scripts.generate_driving_distances_cli.derive_origins_and_destinations')
    @patch('python.scripts.generate_driving_distances_cli.PollingModelConfig')
    def test_check_bad_locations_exits_zero_when_all_routed(
        self, mock_cfg_cls, mock_derive, mock_build, unused_mock_reach, tmp_path,
    ):
        '''--check-bad-locations exits 0 when every origin routed.'''
        del unused_mock_reach
        mock_cfg_cls.load_config.return_value = MagicMock(
            location='Gwinnett_GA', census_year='2020',
            config_file_path=str(tmp_path / 'cfg.yaml'),
        )
        mock_derive.return_value = (
            {'block_ok': [-84.0, 33.9], 'poll_x': [-84.1, 34.0]},
            ['block_ok'],
            ['poll_x'],
        )
        mock_build.return_value = pd.DataFrame({
            'id_orig': ['block_ok'], 'id_dest': ['poll_x'], 'distance_m': [12345.0],
        })
        logdir = tmp_path / 'logs'
        os.makedirs(logdir, exist_ok=True)
        rc = main([
            '--state', 'georgia',
            '-l', str(tmp_path / 'cfg.yaml'),
            '--logdir', str(logdir),
            '--check-bad-locations',
        ])
        assert rc == 0

    @patch('python.scripts.generate_driving_distances_cli._assert_ors_reachable')
    @patch('python.scripts.generate_driving_distances_cli.build_distance_matrix')
    @patch('python.scripts.generate_driving_distances_cli.derive_origins_and_destinations')
    @patch('python.scripts.generate_driving_distances_cli.PollingModelConfig')
    def test_write_path_exits_nonzero_but_still_writes_partial_csv(
        self, mock_cfg_cls, mock_derive, mock_build, unused_mock_reach, tmp_path, capsys,
    ):
        '''An unrouted origin fails the run loudly, but completed work is kept.

        Per #325: write the partial CSV (composes with resume), exit non-zero,
        and enumerate exactly which origins are missing with id + lat/lon.
        '''
        del unused_mock_reach
        mock_cfg_cls.load_config.return_value = MagicMock(
            location='Gwinnett_GA', census_year='2020',
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

        driving_dir = tmp_path / 'datasets' / 'driving' / 'Gwinnett_GA'
        logdir = tmp_path / 'logs'
        os.makedirs(driving_dir, exist_ok=True)
        os.makedirs(logdir, exist_ok=True)
        expected_output = driving_dir / 'Gwinnett_GA_driving_distances.csv'

        with patch(
            'python.scripts.generate_driving_distances_cli.build_output_csv_path',
            return_value=str(expected_output),
        ):
            rc = main([
                '--state', 'georgia',
                '-l', str(tmp_path / 'cfg.yaml'),
                '--logdir', str(logdir),
            ])

        assert rc == 1
        # The partial CSV keeps the successfully routed rows.
        written = pd.read_csv(expected_output)
        assert set(written['id_orig']) == {'block_ok'}
        out = capsys.readouterr().out
        assert 'block_bad' in out
        assert '33.91' in out
        assert '-84.05' in out

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
            location='Gwinnett_GA', census_year='2020',
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

        driving_dir = tmp_path / 'datasets' / 'driving' / 'Gwinnett_GA'
        os.makedirs(driving_dir, exist_ok=True)
        expected_output = driving_dir / 'Gwinnett_GA_driving_distances.csv'
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
                '--state', 'georgia',
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
            location='Gwinnett_GA', census_year='2020',
            config_file_path=str(tmp_path / 'cfg.yaml'),
        )
        mock_derive.return_value = (
            {'a': [-84.0, 33.9], 'x': [-84.1, 34.0]},
            ['a'],
            ['x'],
        )

        driving_dir = tmp_path / 'datasets' / 'driving' / 'Gwinnett_GA'
        os.makedirs(driving_dir, exist_ok=True)
        expected_output = driving_dir / 'Gwinnett_GA_driving_distances.csv'
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
                '--state', 'georgia',
                '-l', str(tmp_path / 'cfg.yaml'),
                '--logdir', str(logdir),
            ])

        assert not mock_build.called


class TestStateValidation:
    '''Tests for --state validation and config-derived fallback.'''

    def test_rejects_unknown_state_slug(self, tmp_path):
        '''An explicit --state with an unknown slug must exit non-zero with a clear error.'''
        del tmp_path
        with pytest.raises(SystemExit) as exc_info:
            main(['--state', 'atlantis', '-l', '/nonexistent.yaml'])
        assert exc_info.value.code != 0

    def test_state_flag_no_longer_required_on_cli(self):
        '''argparse should accept --state-less invocation; derivation runs in main().'''
        # This is the bare-parser case; the parser itself must accept it.
        # main() will later try to load the config and derive; that error
        # path is exercised by test_errors_when_neither_flag_nor_derivable_location.
        parser = build_arg_parser()
        args = parser.parse_args(['-l', '/nonexistent.yaml'])
        assert args.state is None


class TestConfigDerivedState:
    '''Tests for deriving the state from config.location when --state is absent.'''

    @patch('python.scripts.generate_driving_distances_cli._assert_ors_reachable')
    @patch('python.scripts.generate_driving_distances_cli.build_distance_matrix')
    @patch('python.scripts.generate_driving_distances_cli.derive_origins_and_destinations')
    @patch('python.scripts.generate_driving_distances_cli.PollingModelConfig')
    def test_derives_state_from_config_location_when_no_flag(
            self, mock_cfg_cls, mock_derive, mock_build, unused_mock_reach, tmp_path):
        '''No --state, config.location='Gwinnett_County_GA' -> state resolves to georgia.

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

    @patch('python.scripts.generate_driving_distances_cli.state_slug_from_location')
    @patch('python.scripts.generate_driving_distances_cli._assert_ors_reachable')
    @patch('python.scripts.generate_driving_distances_cli.build_distance_matrix')
    @patch('python.scripts.generate_driving_distances_cli.derive_origins_and_destinations')
    @patch('python.scripts.generate_driving_distances_cli.PollingModelConfig')
    def test_explicit_state_flag_overrides_config_derivation(
            self, mock_cfg_cls, mock_derive, mock_build, unused_mock_reach, mock_state_derive, tmp_path):
        '''--state texas wins even when config.location would derive to georgia.

        Asserts that the explicit override is accepted (no SystemExit on a
        non-matching state). The script does not fail just because state
        and location disagree — operators may legitimately point at a
        different graph.
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
                '--state', 'texas',
                '-l', str(tmp_path / 'cfg.yaml'),
                '--logdir', str(logdir),
            ])
        assert rc == 0
        mock_state_derive.assert_not_called()

    @patch('python.scripts.generate_driving_distances_cli._assert_ors_reachable')
    @patch('python.scripts.generate_driving_distances_cli.PollingModelConfig')
    def test_errors_when_neither_flag_nor_derivable_location(
            self, mock_cfg_cls, unused_mock_reach):
        '''No --state, config.location='testing' -> exit 2 with actionable error.'''
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
            main(['--state', 'georgia', '-l', '/nonexistent.yaml'])
        assert exc_info.value.code == 1
