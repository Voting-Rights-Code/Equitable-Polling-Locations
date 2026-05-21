'''Tests for python/scripts/generate_driving_distances_cli.py.'''
import os
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


class TestMain:
    '''Smoke-test the end-to-end flow with everything mocked.'''

    @patch('python.scripts.generate_driving_distances_cli.build_distance_matrix')
    @patch('python.scripts.generate_driving_distances_cli.derive_origins_and_destinations')
    @patch('python.scripts.generate_driving_distances_cli.PollingModelConfig')
    def test_writes_csv_at_expected_path(self, mock_cfg_cls, mock_derive, mock_build, tmp_path):
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
                '-l', str(tmp_path / 'cfg.yaml'),
                '--logdir', str(logdir),
            ])

        written = pd.read_csv(driving_dir / 'Gwinnett_GA_driving_distances.csv')
        assert list(written.columns) == ['id_orig', 'id_dest', 'distance_m']
        assert written.iloc[0]['distance_m'] == 12345.0
