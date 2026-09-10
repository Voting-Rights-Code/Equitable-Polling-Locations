'''Tests for python/utils/ors_url.py.'''
import pytest

from python.utils.ors_url import (
    DEFAULT_MATRIX_URL,
    directions_url_from_matrix_url,
    resolve_ors_url,
)


class TestResolveOrsUrl:
    '''URL precedence: CLI override > $ORS_URL > default.'''

    def test_default_when_no_override_and_no_env(self, monkeypatch):
        monkeypatch.delenv('ORS_URL', raising=False)
        assert resolve_ors_url() == DEFAULT_MATRIX_URL

    def test_env_var_when_no_cli_override(self, monkeypatch):
        monkeypatch.setenv('ORS_URL', 'http://example:9090/ors/v2/matrix/driving-car')
        assert resolve_ors_url() == 'http://example:9090/ors/v2/matrix/driving-car'

    def test_cli_override_wins_over_env(self, monkeypatch):
        monkeypatch.setenv('ORS_URL', 'http://env-url:9090/ors/v2/matrix/driving-car')
        result = resolve_ors_url('http://cli-url:7070/ors/v2/matrix/driving-car')
        assert result == 'http://cli-url:7070/ors/v2/matrix/driving-car'

    def test_empty_string_cli_override_falls_back_to_env(self, monkeypatch):
        monkeypatch.setenv('ORS_URL', 'http://env-url:9090/ors/v2/matrix/driving-car')
        assert resolve_ors_url('') == 'http://env-url:9090/ors/v2/matrix/driving-car'


class TestDirectionsUrlFromMatrixUrl:
    '''Derive single-pair directions URL from the matrix URL.'''

    def test_swaps_matrix_segment_for_directions(self):
        assert directions_url_from_matrix_url(
            'http://localhost:8080/ors/v2/matrix/driving-car'
        ) == 'http://localhost:8080/ors/v2/directions/driving-car'

    def test_preserves_host_and_profile(self):
        assert directions_url_from_matrix_url(
            'https://api.openrouteservice.org/v2/matrix/cycling-regular'
        ) == 'https://api.openrouteservice.org/v2/directions/cycling-regular'

    def test_raises_when_no_matrix_segment(self):
        with pytest.raises(ValueError, match='matrix'):
            directions_url_from_matrix_url('http://localhost:8080/ors/v2/health')
