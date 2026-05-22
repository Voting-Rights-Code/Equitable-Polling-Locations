'''Tests for python/utils/ors_setup.py.'''
import os
from unittest.mock import patch

import pytest

from python.utils.ors_setup import (
    GEOFABRIK_BASE_URL,
    GEOFABRIK_STATE_SLUGS,
    ORS_DATA_DIR,
    download_pbf_if_missing,
    geofabrik_url,
    pbf_path,
)


class TestSlugTable:
    '''Sanity checks on the GEOFABRIK_STATE_SLUGS set.'''

    def test_contains_all_50_states_plus_dc(self):
        '''The slug table should have exactly 51 entries (50 states + DC).'''
        assert len(GEOFABRIK_STATE_SLUGS) == 51

    def test_contains_georgia(self):
        assert 'georgia' in GEOFABRIK_STATE_SLUGS

    def test_contains_district_of_columbia(self):
        '''DC's Geofabrik slug is hyphenated, not abbreviated.'''
        assert 'district-of-columbia' in GEOFABRIK_STATE_SLUGS

    def test_contains_new_york_with_hyphen(self):
        '''Multi-word states use hyphens in their Geofabrik slugs.'''
        assert 'new-york' in GEOFABRIK_STATE_SLUGS

    def test_excludes_uppercase_postal_codes(self):
        '''Postal codes like "GA" must not appear; slugs only.'''
        assert 'GA' not in GEOFABRIK_STATE_SLUGS
        assert 'NY' not in GEOFABRIK_STATE_SLUGS


class TestGeofabrikUrl:
    '''Tests for ``geofabrik_url``.'''

    def test_builds_url_for_known_slug(self):
        assert geofabrik_url('georgia') == f'{GEOFABRIK_BASE_URL}/georgia-latest.osm.pbf'

    def test_builds_url_for_hyphenated_slug(self):
        assert geofabrik_url('new-york') == f'{GEOFABRIK_BASE_URL}/new-york-latest.osm.pbf'

    def test_raises_value_error_for_unknown_slug(self):
        with pytest.raises(ValueError, match='unknown state slug'):
            geofabrik_url('atlantis')


class TestPbfPath:
    '''Tests for ``pbf_path``.'''

    def test_returns_path_under_ors_data_dir(self):
        result = pbf_path('georgia')
        assert result.endswith(os.path.join('datasets', 'openrouteservice',
                                            'georgia-latest.osm.pbf'))
        assert ORS_DATA_DIR in result


class TestDownloadPbfIfMissing:
    '''Tests for ``download_pbf_if_missing``.'''

    def test_skips_download_when_file_present(self, tmp_path):
        '''If the target file already exists, urlretrieve must not be called.'''
        with patch('python.utils.ors_setup.ORS_DATA_DIR', str(tmp_path)):
            with patch('python.utils.ors_setup.pbf_path',
                       return_value=str(tmp_path / 'georgia-latest.osm.pbf')):
                target = tmp_path / 'georgia-latest.osm.pbf'
                target.write_bytes(b'fake pbf data')
                with patch('python.utils.ors_setup.urllib.request.urlretrieve') as mock_retrieve:
                    result = download_pbf_if_missing('georgia')
                    assert result == str(target)
                    mock_retrieve.assert_not_called()

    def test_calls_urlretrieve_when_file_absent(self, tmp_path):
        '''If the target file does not exist, urlretrieve must be called with a
        .partial path; on success the final file exists and no .partial remains.'''
        with patch('python.utils.ors_setup.ORS_DATA_DIR', str(tmp_path)):
            target_path = str(tmp_path / 'georgia-latest.osm.pbf')
            partial_path = f'{target_path}.partial'
            with patch('python.utils.ors_setup.pbf_path', return_value=target_path):
                def fake_retrieve(url, target):
                    del url
                    with open(target, 'wb') as fh:
                        fh.write(b'fake pbf data')
                with patch('python.utils.ors_setup.urllib.request.urlretrieve',
                           side_effect=fake_retrieve) as mock_retrieve:
                    result = download_pbf_if_missing('georgia')
                    assert result == target_path
                    mock_retrieve.assert_called_once()
                    args, _ = mock_retrieve.call_args
                    assert args[0] == f'{GEOFABRIK_BASE_URL}/georgia-latest.osm.pbf'
                    assert args[1] == partial_path
                    assert os.path.exists(target_path), 'final .pbf must exist'
                    assert not os.path.exists(partial_path), '.partial must not remain after success'

    def test_raises_value_error_for_unknown_slug(self):
        with pytest.raises(ValueError, match='unknown state slug'):
            download_pbf_if_missing('atlantis')
