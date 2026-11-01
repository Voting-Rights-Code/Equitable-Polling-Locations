"""Tests for census key loading from credentials.json and CENSUS_API_KEY env var."""

import json

import pytest
from unittest.mock import patch

from python.utils.pull_census_data import _load_census_key
from python.utils.pull_census_data import pull_census_data


@pytest.fixture(autouse=True)
def _clear_census_env(monkeypatch):
    """Ensure CENSUS_API_KEY is unset unless a test explicitly sets it."""
    monkeypatch.delenv("CENSUS_API_KEY", raising=False)


class TestLoadCensusKey:
    """Tests for _load_census_key()."""

    def test_returns_key_when_valid_json(self, tmp_path):
        """Valid JSON with census_key field returns the key string."""
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text(json.dumps({"census_key": "test-key-123"}))
        result = _load_census_key(creds_file)
        assert result == "test-key-123"

    def test_returns_none_when_file_missing(self, tmp_path):
        """Missing file returns None."""
        creds_file = tmp_path / "credentials.json"
        result = _load_census_key(creds_file)
        assert result is None

    def test_returns_none_when_malformed_json(self, tmp_path):
        """Malformed JSON returns None."""
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text("not valid json{{{")
        result = _load_census_key(creds_file)
        assert result is None

    def test_returns_none_when_key_field_absent(self, tmp_path):
        """Valid JSON without census_key field returns None."""
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text(json.dumps({"other_key": "value"}))
        result = _load_census_key(creds_file)
        assert result is None

    def test_returns_env_var_when_set(self, tmp_path, monkeypatch):
        """CENSUS_API_KEY env var returns its value when credentials file is missing."""
        monkeypatch.setenv("CENSUS_API_KEY", "env-key-xyz")
        creds_file = tmp_path / "credentials.json"
        result = _load_census_key(creds_file)
        assert result == "env-key-xyz"

    def test_env_var_takes_precedence_over_file(self, tmp_path, monkeypatch):
        """CENSUS_API_KEY wins over credentials.json when both are present."""
        monkeypatch.setenv("CENSUS_API_KEY", "env-key-xyz")
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text(json.dumps({"census_key": "file-key-abc"}))
        result = _load_census_key(creds_file)
        assert result == "env-key-xyz"

    def test_empty_env_var_falls_through_to_file(self, tmp_path, monkeypatch):
        """Empty CENSUS_API_KEY is treated as unset; file is consulted."""
        monkeypatch.setenv("CENSUS_API_KEY", "")
        creds_file = tmp_path / "credentials.json"
        creds_file.write_text(json.dumps({"census_key": "file-key-abc"}))
        result = _load_census_key(creds_file)
        assert result == "file-key-abc"


class TestPullCensusDataKeyHandling:
    """Tests for pull_census_data() census key resolution."""

    @patch("python.utils.pull_census_data._load_census_key", return_value=None)
    def test_raises_valueerror_when_no_key_available(self, _mock_loader):
        """pull_census_data raises ValueError when no apikey is provided and loader returns None."""
        # state_lookup={} is safe — ValueError fires before state_lookup is used
        with pytest.raises(ValueError, match="No census key available"):
            pull_census_data("GA", "Gwinnett County", "2020", apikey=None, state_lookup={})
