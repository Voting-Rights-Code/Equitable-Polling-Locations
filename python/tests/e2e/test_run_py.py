"""Tests for run.py e2e_tests command support."""

import subprocess
import sys

import pytest


@pytest.mark.e2e
@pytest.mark.e2e_csv
class TestRunPyE2eCommand:
    """Verify run.py accepts the e2e_tests command."""

    def test_e2e_tests_help_does_not_error(self):
        """run.py e2e_tests --help should not produce an argparse error."""
        result = subprocess.run(
            [sys.executable, 'run.py', 'e2e_tests', '--help'],
            capture_output=True, text=True, timeout=10,
        )
        # It will fail because Docker isn't running pytest with --help,
        # but it should NOT fail with "invalid choice: 'e2e_tests'"
        assert 'invalid choice' not in result.stderr
