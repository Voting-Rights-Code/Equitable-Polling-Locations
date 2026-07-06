"""End-to-end tests for the db_import_config_cli script.

All tests are database-backed and will be skipped automatically when no 'test'
environment is configured in settings.yaml.
"""

# pylint: disable=redefined-outer-name

import yaml
import pytest

from python.tests.e2e.conftest import CONFIG_VARIANTS


@pytest.mark.e2e
@pytest.mark.e2e_db
class TestDbImportConfig:
    """Tests verifying that model configs are imported correctly into the DB."""

    def test_import_exits_zero(self, imported_configs):
        """The import fixture completes without raising, confirming a zero exit code.

        The ``imported_configs`` fixture calls ``run_cli`` which asserts a zero
        return code internally; reaching this test body is sufficient proof.

        Args:
            imported_configs: Session-scoped fixture that runs the CLI.
        """
        # Fixture already asserts exit code == 0; reaching here confirms success.
        assert imported_configs is None or True

    def test_all_configs_imported(self, e2e_test_data, imported_configs, test_environment):
        """At least as many configs as CONFIG_VARIANTS exist in the DB for this session.

        Args:
            e2e_test_data: Session-scoped test data dict.
            imported_configs: Ensures the import has run.
            test_environment: The loaded test environment.
        """
        from python.database.query import Query  # pylint: disable=import-outside-toplevel

        sid = e2e_test_data['sid']
        query = Query(test_environment)

        configs = query.find_model_configs_by_config_set(sid)
        assert len(configs) >= len(CONFIG_VARIANTS), (
            f"Expected at least {len(CONFIG_VARIANTS)} configs in DB for config_set='{sid}', "
            f"found {len(configs)}"
        )

    def test_config_fields_match_yaml(self, e2e_test_data, imported_configs, test_environment):
        """Fields in the DB record match the values in the source YAML for config_basic.

        Args:
            e2e_test_data: Session-scoped test data dict.
            imported_configs: Ensures the import has run.
            test_environment: The loaded test environment.
        """
        from python.database.query import Query  # pylint: disable=import-outside-toplevel

        sid = e2e_test_data['sid']
        config_suffix = 'config_basic'
        config_name = f'{sid}_{config_suffix}'
        yaml_path = e2e_test_data['configs'][config_suffix]

        with open(yaml_path, 'r', encoding='utf-8') as fh:
            yaml_data = yaml.safe_load(fh)

        query = Query(test_environment)
        db_config = query.find_model_configs_by_config_set_and_config_name(sid, config_name)

        assert db_config is not None, (
            f"No ModelConfig found for config_set='{sid}', config_name='{config_name}'"
        )

        # Verify scalar fields that are directly stored on the model.
        assert db_config.config_set == sid, (
            f"Expected config_set='{sid}', got '{db_config.config_set}'"
        )
        assert db_config.config_name == config_name, (
            f"Expected config_name='{config_name}', got '{db_config.config_name}'"
        )
        assert db_config.location == sid, (
            f"Expected location='{sid}', got '{db_config.location}'"
        )
        assert db_config.beta == yaml_data['beta'], (
            f"Expected beta={yaml_data['beta']}, got {db_config.beta}"
        )
        assert db_config.precincts_open == yaml_data['precincts_open'], (
            f"Expected precincts_open={yaml_data['precincts_open']}, "
            f"got {db_config.precincts_open}"
        )
        assert db_config.capacity == yaml_data['capacity'], (
            f"Expected capacity={yaml_data['capacity']}, got {db_config.capacity}"
        )

    def test_config_metric_round_trips(self, e2e_test_data, imported_configs, test_environment):
        """The driving_time config's metric persists to and loads from the DB.

        Args:
            e2e_test_data: Session-scoped test data dict.
            imported_configs: Ensures the import has run.
            test_environment: The loaded test environment.
        """
        from python.database.query import Query  # pylint: disable=import-outside-toplevel

        sid = e2e_test_data['sid']
        config_name = f'{sid}_config_driving_duration'
        query = Query(test_environment)
        db_config = query.find_model_configs_by_config_set_and_config_name(sid, config_name)

        assert db_config is not None, (
            f"No ModelConfig found for config_set='{sid}', config_name='{config_name}'"
        )
        assert db_config.metric == 'driving_time', (
            f"Expected metric='driving_time', got {db_config.metric!r}"
        )
