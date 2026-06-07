'''Tests for python/utils/ors_client.py.'''
from unittest.mock import MagicMock, patch

import pytest

from python.utils.ors_client import (
    OrsMatrixError,
    query_directions,
    query_matrix,
)

MATRIX_URL = 'http://ors:8080/ors/v2/matrix/driving-car'
DIRECTIONS_URL = 'http://ors:8080/ors/v2/directions/driving-car'


class TestQueryMatrix:
    '''Matrix POST body shape and response parsing.'''

    @patch('python.utils.ors_client.requests.post')
    def test_posts_expected_body(self, mock_post):
        mock_post.return_value = MagicMock(text='{"distances": [[0, 100], [100, 0]]}')
        locations = [[-84.0, 33.9], [-84.1, 34.0]]
        query_matrix(locations, sources=[0], dests=[1], server=MATRIX_URL)
        call = mock_post.call_args
        assert call.kwargs['json'] == {
            'locations': locations,
            'destinations': [1],
            'metrics': ['distance'],
            'sources': [0],
        }
        assert call.kwargs['headers']['Content-Type'] == 'application/json; charset=utf-8'

    @patch('python.utils.ors_client.requests.post')
    def test_omits_auth_header_when_no_key(self, mock_post):
        mock_post.return_value = MagicMock(text='{"distances": [[0]]}')
        query_matrix([[0.0, 0.0]], [0], [0], MATRIX_URL)
        assert 'Authorization' not in mock_post.call_args.kwargs['headers']

    @patch('python.utils.ors_client.requests.post')
    def test_includes_auth_header_when_key_provided(self, mock_post):
        mock_post.return_value = MagicMock(text='{"distances": [[0]]}')
        query_matrix([[0.0, 0.0]], [0], [0], MATRIX_URL, key='SECRET')
        assert mock_post.call_args.kwargs['headers']['Authorization'] == 'SECRET'

    @patch('python.utils.ors_client.requests.post')
    def test_returns_distances_array(self, mock_post):
        mock_post.return_value = MagicMock(text='{"distances": [[0, 100], [100, 0]]}')
        result = query_matrix([[-84.0, 33.9], [-84.1, 34.0]], [0], [1], MATRIX_URL)
        assert result == [[0, 100], [100, 0]]

    @patch('python.utils.ors_client.requests.post')
    def test_raises_ors_matrix_error_on_api_error(self, mock_post):
        mock_post.return_value = MagicMock(
            text='{"error": {"code": 6010, "message": "Unable to build matrix"}}'
        )
        with pytest.raises(OrsMatrixError, match='6010'):
            query_matrix([[-84.0, 33.9], [-84.1, 34.0]], [0], [1], MATRIX_URL)

    @patch('python.utils.ors_client.requests.post')
    def test_metric_kwarg_plumbs_through(self, mock_post):
        mock_post.return_value = MagicMock(text='{"distances": [[0]]}')
        query_matrix([[0.0, 0.0]], [0], [0], MATRIX_URL, metric='duration')
        assert mock_post.call_args.kwargs['json']['metrics'] == ['duration']


class TestQueryDirections:
    '''Single-pair directions GET and parsing.'''

    @patch('python.utils.ors_client.requests.get')
    def test_returns_distance_in_meters(self, mock_get):
        mock_get.return_value = MagicMock(
            text='{"features": [{"properties": {"segments": [{"distance": 12345.6}]}}]}'
        )
        result = query_directions([-84.0, 33.9], [-84.1, 34.0], DIRECTIONS_URL)
        assert result == 12345.6

    @patch('python.utils.ors_client.requests.get')
    def test_returns_none_on_ors_error(self, mock_get):
        mock_get.return_value = MagicMock(
            text='{"error": {"code": 2099, "message": "Unable to find a route"}}'
        )
        assert query_directions([-84.0, 33.9], [-84.1, 34.0], DIRECTIONS_URL) is None

    @patch('python.utils.ors_client.requests.get')
    def test_url_includes_start_and_end_params(self, mock_get):
        mock_get.return_value = MagicMock(
            text='{"features": [{"properties": {"segments": [{"distance": 1.0}]}}]}'
        )
        query_directions([-84.0, 33.9], [-84.1, 34.0], DIRECTIONS_URL)
        url = mock_get.call_args.args[0]
        assert 'start=-84.0,33.9' in url
        assert 'end=-84.1,34.0' in url

    @patch('python.utils.ors_client.requests.get')
    def test_returns_none_on_malformed_success_payload(self, mock_get):
        mock_get.return_value = MagicMock(text='{"features": []}')
        assert query_directions([-84.0, 33.9], [-84.1, 34.0], DIRECTIONS_URL) is None
