'''Tests for python/utils/ors_status.py.'''
import json
import urllib.error
from unittest.mock import MagicMock, patch

import pytest

from python.utils.ors_status import verify_loaded_state


MATRIX_URL = 'http://localhost:8080/ors/v2/matrix/driving-car'


def _mock_urlopen_returning(payload):
    '''Return a urlopen mock whose context-manager yields ``payload`` as JSON bytes.'''
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode('utf-8')
    mock = MagicMock()
    mock.__enter__.return_value = response
    return mock


class TestVerifyLoadedState:
    '''Tests for ``verify_loaded_state``.'''

    @patch('python.utils.ors_status.urllib.request.urlopen')
    def test_returns_silently_when_source_file_matches(self, mock_urlopen):
        '''Matching source_file should return None without raising.'''
        payload = {
            'profiles': {
                'driving-car': {
                    'source_file': '/home/ors/files/georgia-latest.osm.pbf',
                },
            },
        }
        mock_urlopen.return_value = _mock_urlopen_returning(payload)
        assert verify_loaded_state('georgia', MATRIX_URL) is None

    @patch('python.utils.ors_status.urllib.request.urlopen')
    def test_raises_when_source_file_mismatches(self, mock_urlopen):
        '''Mismatched source_file must raise RuntimeError mentioning both filenames.'''
        payload = {
            'profiles': {
                'driving-car': {
                    'source_file': '/home/ors/files/texas-latest.osm.pbf',
                },
            },
        }
        mock_urlopen.return_value = _mock_urlopen_returning(payload)
        with pytest.raises(RuntimeError) as exc_info:
            verify_loaded_state('georgia', MATRIX_URL)
        assert 'texas-latest.osm.pbf' in str(exc_info.value)
        assert 'georgia-latest.osm.pbf' in str(exc_info.value)

    @patch('python.utils.ors_status.urllib.request.urlopen')
    def test_raises_when_source_file_missing_from_every_profile(self, mock_urlopen):
        '''No source_file field anywhere → RuntimeError mentioning schema drift.'''
        payload = {
            'profiles': {
                'driving-car': {
                    'extent': [-85.7, 30.3, -80.7, 35.1],
                },
            },
        }
        mock_urlopen.return_value = _mock_urlopen_returning(payload)
        with pytest.raises(RuntimeError) as exc_info:
            verify_loaded_state('georgia', MATRIX_URL)
        assert 'no source_file' in str(exc_info.value)
        assert 'georgia-latest.osm.pbf' in str(exc_info.value)

    @patch('python.utils.ors_status.urllib.request.urlopen')
    def test_returns_silently_when_status_endpoint_unreachable(self, mock_urlopen, capsys):
        '''URLError on the status fetch should warn and return, not raise.'''
        mock_urlopen.side_effect = urllib.error.URLError('connection refused')
        assert verify_loaded_state('georgia', MATRIX_URL) is None
        captured = capsys.readouterr()
        assert 'could not fetch' in captured.out

    @patch('python.utils.ors_status.urllib.request.urlopen')
    def test_returns_silently_when_response_is_malformed_json(self, mock_urlopen, capsys):
        '''Non-JSON response should warn and return, not raise.'''
        response = MagicMock()
        response.read.return_value = b'<html>not json</html>'
        mock = MagicMock()
        mock.__enter__.return_value = response
        mock_urlopen.return_value = mock
        assert verify_loaded_state('georgia', MATRIX_URL) is None
        captured = capsys.readouterr()
        assert 'could not fetch' in captured.out

    @patch('python.utils.ors_status.urllib.request.urlopen')
    def test_derives_status_url_from_matrix_url(self, mock_urlopen):
        '''The status URL must be derived by stripping /matrix/... from the matrix URL.'''
        payload = {
            'profiles': {
                'driving-car': {
                    'source_file': '/home/ors/files/georgia-latest.osm.pbf',
                },
            },
        }
        mock_urlopen.return_value = _mock_urlopen_returning(payload)
        verify_loaded_state('georgia', 'http://localhost:8080/ors/v2/matrix/driving-car')
        called_url = mock_urlopen.call_args.args[0]
        assert called_url == 'http://localhost:8080/ors/v2/status'
