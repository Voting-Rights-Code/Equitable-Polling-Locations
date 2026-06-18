"""Tests for GMAP Platform API key loading in GMAP_data.py."""

from unittest.mock import patch

from python.utils.GMAP_data import _load_gmap_key


class TestLoadGmapKey:
    """Tests for _load_gmap_key()."""

    @patch("python.utils.GMAP_data.secret_store.resolve")
    @patch("python.utils.GMAP_data.secret_store.get_secret")
    def test_resolves_via_secret_store(self, mock_get_secret, mock_resolve):
        """_load_gmap_key looks up the 'gmap' secret and returns its resolved value."""
        mock_get_secret.return_value = "the-gmap-secret"
        mock_resolve.return_value = "resolved-key-123"

        result = _load_gmap_key()

        mock_get_secret.assert_called_once_with("gmap")
        mock_resolve.assert_called_once_with("the-gmap-secret")
        assert result == "resolved-key-123"

    @patch("python.utils.GMAP_data.secret_store.resolve", return_value=None)
    def test_returns_none_when_unresolved(self, _mock_resolve):
        """_load_gmap_key returns None when secret_store has no value for any backend."""
        assert _load_gmap_key() is None
