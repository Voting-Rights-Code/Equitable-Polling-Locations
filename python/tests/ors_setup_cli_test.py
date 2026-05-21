'''Tests for python/scripts/ors_setup_cli.py.'''
from unittest.mock import patch, MagicMock

import pytest

from python.scripts.ors_setup_cli import (
    GEOFABRIK_BASE_URL,
    STATE_TO_GEOFABRIK_SLUG,
    build_geofabrik_url,
    _ensure_host_only,
    main,
)


class TestGeofabrikUrlMapping:
    '''Tests for build_geofabrik_url state-code to URL mapping.'''

    def test_simple_state(self):
        assert build_geofabrik_url('GA') == f'{GEOFABRIK_BASE_URL}/georgia-latest.osm.pbf'

    def test_hyphenated_state_two_words(self):
        assert build_geofabrik_url('NY') == f'{GEOFABRIK_BASE_URL}/new-york-latest.osm.pbf'

    def test_district_of_columbia(self):
        assert build_geofabrik_url('DC') == \
            f'{GEOFABRIK_BASE_URL}/district-of-columbia-latest.osm.pbf'

    def test_unsupported_territory_raises(self):
        with pytest.raises(ValueError, match='not supported'):
            build_geofabrik_url('PR')

    def test_unknown_code_raises(self):
        with pytest.raises(ValueError, match='unknown'):
            build_geofabrik_url('ZZ')


class TestStateSlugTableCoverage:
    '''Sanity check: the slug table must cover all 50 states + DC.'''

    def test_has_50_states_plus_dc(self):
        # 50 states + DC = 51 entries.
        assert len(STATE_TO_GEOFABRIK_SLUG) == 51


class TestHostOnlyCheck:
    '''Tests for _ensure_host_only dev-container detection.'''

    @patch('os.path.exists', return_value=True)
    def test_refuses_inside_dev_container(self, unused_mock_exists):
        del unused_mock_exists
        with pytest.raises(SystemExit):
            _ensure_host_only()

    @patch('os.path.exists', return_value=False)
    def test_allows_on_host(self, unused_mock_exists):
        del unused_mock_exists
        _ensure_host_only()   # No exception.


class TestMainDownload:
    '''End-to-end main() path with download mocked.'''

    @patch('python.scripts.ors_setup_cli.urllib.request.urlretrieve')
    @patch('python.scripts.ors_setup_cli._ensure_host_only')
    def test_downloads_to_devcontainer_ors_data(self, unused_mock_host, mock_retrieve, tmp_path):
        del unused_mock_host
        out_dir = tmp_path / 'ors_data'
        mock_retrieve.return_value = (str(out_dir / 'georgia-latest.osm.pbf'), MagicMock())

        with patch('python.scripts.ors_setup_cli.ORS_DATA_DIR', str(out_dir)):
            main(['--state', 'GA'])

        # Validate the URL passed to urlretrieve.
        assert mock_retrieve.call_args.args[0] == \
            f'{GEOFABRIK_BASE_URL}/georgia-latest.osm.pbf'

    @patch('python.scripts.ors_setup_cli.urllib.request.urlretrieve')
    @patch('python.scripts.ors_setup_cli._ensure_host_only')
    def test_skips_when_file_exists_without_force(self, unused_mock_host, mock_retrieve, tmp_path):
        del unused_mock_host
        out_dir = tmp_path / 'ors_data'
        out_dir.mkdir()
        existing = out_dir / 'georgia-latest.osm.pbf'
        existing.write_bytes(b'pretend pbf')
        with patch('python.scripts.ors_setup_cli.ORS_DATA_DIR', str(out_dir)):
            main(['--state', 'GA'])
        assert not mock_retrieve.called

    @patch('python.scripts.ors_setup_cli.urllib.request.urlretrieve')
    @patch('python.scripts.ors_setup_cli._ensure_host_only')
    def test_force_redownloads(self, unused_mock_host, mock_retrieve, tmp_path):
        del unused_mock_host
        out_dir = tmp_path / 'ors_data'
        out_dir.mkdir()
        (out_dir / 'georgia-latest.osm.pbf').write_bytes(b'old')
        mock_retrieve.return_value = (str(out_dir / 'georgia-latest.osm.pbf'), MagicMock())
        with patch('python.scripts.ors_setup_cli.ORS_DATA_DIR', str(out_dir)):
            main(['--state', 'GA', '--force'])
        assert mock_retrieve.called
