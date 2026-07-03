'''Tests for python/utils/ors_client.py.'''
from unittest.mock import MagicMock, patch

import pytest

from python.utils.ors_client import (
    OrsMatrixError,
    query_directions,
    query_matrix,
    query_route_geometry,
)

MATRIX_URL = 'http://ors:8080/ors/v2/matrix/driving-car'
DIRECTIONS_URL = 'http://ors:8080/ors/v2/directions/driving-car'


class TestQueryMatrix:
    '''Matrix POST body shape and response parsing.'''

    @patch('python.utils.ors_client.requests.post')
    def test_posts_both_metrics_by_default(self, mock_post):
        mock_post.return_value = MagicMock(
            text='{"distances": [[0, 100], [100, 0]], "durations": [[0, 9], [9, 0]]}')
        locations = [[-84.0, 33.9], [-84.1, 34.0]]
        query_matrix(locations, sources=[0], dests=[1], server=MATRIX_URL)
        call = mock_post.call_args
        assert call.kwargs['json'] == {
            'locations': locations,
            'destinations': [1],
            'metrics': ['distance', 'duration'],
            'sources': [0],
        }
        assert call.kwargs['headers']['Content-Type'] == 'application/json; charset=utf-8'

    @patch('python.utils.ors_client.requests.post')
    def test_returns_both_grids_keyed_by_metric(self, mock_post):
        mock_post.return_value = MagicMock(
            text='{"distances": [[0, 100], [100, 0]], "durations": [[0, 9], [9, 0]]}')
        result = query_matrix([[-84.0, 33.9], [-84.1, 34.0]], [0], [1], MATRIX_URL)
        assert result == {'distance': [[0, 100], [100, 0]], 'duration': [[0, 9], [9, 0]]}

    @patch('python.utils.ors_client.requests.post')
    def test_requesting_only_distance_returns_only_distance(self, mock_post):
        mock_post.return_value = MagicMock(text='{"distances": [[0]]}')
        result = query_matrix([[0.0, 0.0]], [0], [0], MATRIX_URL, metrics=('distance',))
        assert mock_post.call_args.kwargs['json']['metrics'] == ['distance']
        assert result == {'distance': [[0]]}

    @patch('python.utils.ors_client.requests.post')
    def test_omits_auth_header_when_no_key(self, mock_post):
        mock_post.return_value = MagicMock(text='{"distances": [[0]], "durations": [[0]]}')
        query_matrix([[0.0, 0.0]], [0], [0], MATRIX_URL)
        assert 'Authorization' not in mock_post.call_args.kwargs['headers']

    @patch('python.utils.ors_client.requests.post')
    def test_includes_auth_header_when_key_provided(self, mock_post):
        mock_post.return_value = MagicMock(text='{"distances": [[0]], "durations": [[0]]}')
        query_matrix([[0.0, 0.0]], [0], [0], MATRIX_URL, key='SECRET')
        assert mock_post.call_args.kwargs['headers']['Authorization'] == 'SECRET'

    @patch('python.utils.ors_client.requests.post')
    def test_raises_ors_matrix_error_on_api_error(self, mock_post):
        mock_post.return_value = MagicMock(
            text='{"error": {"code": 6010, "message": "Unable to build matrix"}}')
        with pytest.raises(OrsMatrixError, match='6010'):
            query_matrix([[-84.0, 33.9], [-84.1, 34.0]], [0], [1], MATRIX_URL)


class TestQueryDirections:
    '''Single-pair directions GET and parsing.'''

    @patch('python.utils.ors_client.requests.get')
    def test_returns_distance_and_duration(self, mock_get):
        mock_get.return_value = MagicMock(
            text='{"features": [{"properties": {"segments": '
                 '[{"distance": 12345.6, "duration": 678.9}]}}]}')
        result = query_directions([-84.0, 33.9], [-84.1, 34.0], DIRECTIONS_URL)
        assert result == (12345.6, 678.9)

    @patch('python.utils.ors_client.requests.get')
    def test_returns_none_on_ors_error(self, mock_get):
        mock_get.return_value = MagicMock(
            text='{"error": {"code": 2099, "message": "Unable to find a route"}}')
        assert query_directions([-84.0, 33.9], [-84.1, 34.0], DIRECTIONS_URL) is None

    @patch('python.utils.ors_client.requests.get')
    def test_url_includes_start_and_end_params(self, mock_get):
        mock_get.return_value = MagicMock(
            text='{"features": [{"properties": {"segments": '
                 '[{"distance": 1.0, "duration": 2.0}]}}]}')
        query_directions([-84.0, 33.9], [-84.1, 34.0], DIRECTIONS_URL)
        url = mock_get.call_args.args[0]
        assert 'start=-84.0,33.9' in url
        assert 'end=-84.1,34.0' in url

    @patch('python.utils.ors_client.requests.get')
    def test_returns_none_on_malformed_success_payload(self, mock_get):
        mock_get.return_value = MagicMock(text='{"features": []}')
        assert query_directions([-84.0, 33.9], [-84.1, 34.0], DIRECTIONS_URL) is None


class TestQueryRouteGeometry:
    '''Single-pair directions GET returning the route polyline.'''

    @patch('python.utils.ors_client.requests.get')
    def test_returns_coordinate_list(self, mock_get):
        mock_get.return_value = MagicMock(
            text='{"features": [{"geometry": {"coordinates": [[-79.9, 39.7], [-79.95, 39.76]]}}]}'
        )
        result = query_route_geometry([-79.9, 39.7], [-79.95, 39.76], DIRECTIONS_URL)
        assert result == [[-79.9, 39.7], [-79.95, 39.76]]

    @patch('python.utils.ors_client.requests.get')
    def test_returns_none_on_ors_error(self, mock_get):
        mock_get.return_value = MagicMock(
            text='{"error": {"code": 2099, "message": "Unable to find a route"}}'
        )
        assert query_route_geometry([-79.9, 39.7], [-79.95, 39.76], DIRECTIONS_URL) is None

    @patch('python.utils.ors_client.requests.get')
    def test_returns_none_on_malformed_payload(self, mock_get):
        mock_get.return_value = MagicMock(text='{"features": []}')
        assert query_route_geometry([-79.9, 39.7], [-79.95, 39.76], DIRECTIONS_URL) is None
