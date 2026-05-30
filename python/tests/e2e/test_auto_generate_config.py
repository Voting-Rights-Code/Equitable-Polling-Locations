"""End-to-end tests for the auto_generate_config CLI template expansion.

These tests verify that auto_generate_config correctly generates YAML config files
from a ``.yaml_template`` file by varying a specified field across a defined range,
and optionally writes the resulting configs to the database.
"""

# pylint: disable=redefined-outer-name

import os

import pytest
import yaml

from python.tests.e2e.conftest import run_cli

MODULE = 'python.scripts.auto_generate_config'

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _generated_config_paths(e2e_test_data: dict) -> list[str]:
    """Return the expected file paths for the two year-varied configs.

    The auto_generate_config script produces filenames of the form
    ``{location}_{field_to_vary}_{value_suffix}.yaml``.  Because location=sid
    and field_to_vary='year' with values [['2020'], ['2022']], the expected
    names are ``{sid}_year_2020.yaml`` and ``{sid}_year_2022.yaml``.

    Args:
        e2e_test_data: The session-scoped test data dict from :func:`e2e_test_data`.

    Returns:
        A list of two absolute paths to the generated YAML files.
    """
    sid = e2e_test_data['sid']
    config_dir = e2e_test_data['config_dir']
    return [
        os.path.join(config_dir, f'{sid}_year_2020.yaml'),
        os.path.join(config_dir, f'{sid}_year_2022.yaml'),
    ]


# ---------------------------------------------------------------------------
# CSV tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.e2e_csv
class TestAutoGenerateConfig:
    """Tests for auto_generate_config template expansion writing to local files."""

    @pytest.fixture(autouse=True)
    def _cleanup_generated(self, e2e_test_data):
        """Remove generated year-varied YAML configs after each test.

        Args:
            e2e_test_data: The session-scoped test data dict from :func:`e2e_test_data`.

        Yields:
            None
        """
        yield
        for path in _generated_config_paths(e2e_test_data):
            if os.path.isfile(path):
                os.remove(path)

    def test_generates_correct_number_of_configs(self, e2e_test_data):
        """Running the CLI with a two-value range creates exactly two YAML files.

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        template_path = e2e_test_data['autogen_template']

        run_cli(MODULE, '-b', template_path)

        generated = _generated_config_paths(e2e_test_data)
        for path in generated:
            assert os.path.isfile(path), (
                f"Expected generated config not found: {path}"
            )
        assert len(generated) == 2, (
            f"Expected 2 generated configs, found {len(generated)}"
        )

    def test_generated_config_has_varied_field(self, e2e_test_data):
        """Each generated YAML contains the correct year value for its variant.

        The template varies 'year' with [['2020'], ['2022']], so each output
        file should have its ``year`` field set to the corresponding list.

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        template_path = e2e_test_data['autogen_template']

        run_cli(MODULE, '-b', template_path)

        expected_years = {
            '_year_2020.yaml': ['2020'],
            '_year_2022.yaml': ['2022'],
        }

        for path in _generated_config_paths(e2e_test_data):
            with open(path, 'r', encoding='utf-8') as fh:
                config = yaml.safe_load(fh)

            filename = os.path.basename(path)
            matched_suffix = next(
                (suffix for suffix in expected_years if filename.endswith(suffix)),
                None,
            )
            assert matched_suffix is not None, (
                f"Unexpected generated file name: {filename}"
            )
            assert config['year'] == expected_years[matched_suffix], (
                f"Expected year={expected_years[matched_suffix]!r} in {filename}, "
                f"got {config['year']!r}"
            )

    def test_generated_config_preserves_other_fields(self, e2e_test_data):
        """Non-varied fields in the generated configs match the template values.

        Verifies that ``beta``, ``capacity``, and ``config_set`` are unchanged
        from the autogen template after generation.

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        template_path = e2e_test_data['autogen_template']
        sid = e2e_test_data['sid']

        with open(template_path, 'r', encoding='utf-8') as fh:
            template = yaml.safe_load(fh)

        run_cli(MODULE, '-b', template_path)

        for path in _generated_config_paths(e2e_test_data):
            with open(path, 'r', encoding='utf-8') as fh:
                config = yaml.safe_load(fh)

            assert config['beta'] == template['beta'], (
                f"Expected beta={template['beta']!r} in {os.path.basename(path)}, "
                f"got {config['beta']!r}"
            )
            assert config['capacity'] == template['capacity'], (
                f"Expected capacity={template['capacity']!r} in {os.path.basename(path)}, "
                f"got {config['capacity']!r}"
            )
            assert config['config_set'] == sid, (
                f"Expected config_set={sid!r} in {os.path.basename(path)}, "
                f"got {config['config_set']!r}"
            )


# ---------------------------------------------------------------------------
# DB tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.e2e_db
class TestAutoGenerateConfigDb:
    """Tests for auto_generate_config writing generated configs to the database."""

    @pytest.fixture(autouse=True)
    def _cleanup_generated(self, e2e_test_data):
        """Remove generated year-varied YAML configs after each test.

        Args:
            e2e_test_data: The session-scoped test data dict from :func:`e2e_test_data`.

        Yields:
            None
        """
        yield
        for path in _generated_config_paths(e2e_test_data):
            if os.path.isfile(path):
                os.remove(path)

    def test_generate_with_db_flag(self, e2e_test_data, test_environment):
        """Running with -d -e test writes the generated configs to the database.

        Uses ``Query.find_model_configs_by_config_set`` to verify that at least
        two configs with 'year' in their name appear in the database after the
        CLI run.

        Args:
            e2e_test_data: Session-scoped test data dict.
            test_environment: The loaded test environment.
        """
        from python.database.query import Query  # pylint: disable=import-outside-toplevel

        template_path = e2e_test_data['autogen_template']
        sid = e2e_test_data['sid']

        run_cli(MODULE, '-b', template_path, '-d', '-e', 'test')

        query = Query(test_environment)
        all_configs = query.find_model_configs_by_config_set(sid)

        year_configs = [c for c in all_configs if 'year' in c.config_name]
        assert len(year_configs) >= 2, (
            f"Expected at least 2 year-varied configs in DB for config_set={sid!r}, "
            f"found {len(year_configs)}: {[c.config_name for c in year_configs]}"
        )
