"""Tests for write_credentials_json() in run.py."""

import json
import pytest

from run import write_credentials_json


class TestWriteCredentialsJson:
    """Tests for write_credentials_json()."""

    def test_writes_valid_json_with_census_key(self, tmp_path):
        """Creates credentials.json with the correct structure."""
        write_credentials_json("test-key-abc", output_dir=tmp_path)
        creds_file = tmp_path / "credentials.json"
        assert creds_file.exists()
        data = json.loads(creds_file.read_text())
        assert data == {"census_key": "test-key-abc"}

    def test_creates_directory_if_missing(self, tmp_path):
        """Creates the output directory if it does not exist."""
        nested = tmp_path / "subdir"
        write_credentials_json("key-123", output_dir=nested)
        assert (nested / "credentials.json").exists()
