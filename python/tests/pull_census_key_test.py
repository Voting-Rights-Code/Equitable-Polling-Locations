"""Tests for census key loading from credentials.json."""

import json

from python.utils.pull_census_data import _load_census_key


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
