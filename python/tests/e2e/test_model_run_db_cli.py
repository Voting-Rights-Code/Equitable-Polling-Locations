"""End-to-end tests for the DB-backed model run CLI (model_run_db_cli).

All tests require configs and distance data to be present in the database,
which is handled by the ``imported_distance_data_all`` and ``imported_configs``
session-scoped fixtures.  Tests that write results back to the database also
require the ``test_environment`` fixture and will be skipped automatically when
no 'test' environment is configured in settings.yaml.
"""

# pylint: disable=redefined-outer-name

import os
import shutil
import sys

import pytest

from python.tests.e2e.conftest import run_cli
from python.utils.directory_constants import RESULTS_BASE_DIR

MODULE = 'python.scripts.model_run_db_cli'


# ---------------------------------------------------------------------------
# Result path helpers
# ---------------------------------------------------------------------------


def _result_dir(session_id: str) -> str:
    """Return the results directory path for a given session ID.

    Args:
        session_id: The e2e session identifier (e.g. ``'e2e_abc123'``).

    Returns:
        Absolute path to ``{RESULTS_BASE_DIR}/{session_id}_results/``.
    """
    return os.path.join(RESULTS_BASE_DIR, f'{session_id}_results')


def _result_files(session_id: str, config_suffix: str) -> dict[str, str]:
    """Return a dict mapping result type names to their expected file paths.

    The file naming convention for DB-sourced runs is:
    ``{session_id}.{session_id}_{config_suffix}_{type}.csv``

    Args:
        session_id: The e2e session identifier.
        config_suffix: The config variant key (e.g. ``'config_basic'``).

    Returns:
        Dict with keys ``results``, ``precinct_distances``,
        ``residence_distances``, and ``edes``, each mapped to an absolute path.
    """
    rdir = _result_dir(session_id)
    prefix = f'{session_id}.{session_id}_{config_suffix}'
    return {
        'results': os.path.join(rdir, f'{prefix}_results.csv'),
        'precinct_distances': os.path.join(rdir, f'{prefix}_precinct_distances.csv'),
        'residence_distances': os.path.join(rdir, f'{prefix}_residence_distances.csv'),
        'edes': os.path.join(rdir, f'{prefix}_edes.csv'),
    }


# ---------------------------------------------------------------------------
# Cleanup fixture
# ---------------------------------------------------------------------------


@pytest.fixture(scope='module', autouse=True)
def cleanup_csv_results(e2e_session_id, pytestconfig):
    """Remove the session's CSV result directory after all tests in this module.

    Args:
        e2e_session_id: The session identifier fixture.
        pytestconfig: The pytest config object, used to read
            ``--keep-e2e-outputs``.

    Yields:
        None
    """
    yield
    rdir = _result_dir(e2e_session_id)
    if not os.path.isdir(rdir):
        return
    if pytestconfig.getoption('--keep-e2e-outputs'):
        print(f'[--keep-e2e-outputs] retained: {rdir}', file=sys.stderr)
    else:
        shutil.rmtree(rdir)


# ---------------------------------------------------------------------------
# Class: TestModelRunDbCliCsvOutput — CSV output tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.e2e_db
class TestModelRunDbCliCsvOutput:
    """Tests verifying that model_run_db_cli writes correct CSV output files."""

    def test_single_config_csv_output(self, e2e_test_data, imported_distance_data_all, imported_configs):
        """Running a single DB config with -o csv produces the expected result file.

        Args:
            e2e_test_data: Session-scoped test data dict.
            imported_distance_data_all: Ensures all distance data is in the DB.
            imported_configs: Ensures all configs are in the DB.
        """
        sid = e2e_test_data['sid']
        config_ref = f'{sid}/{sid}_config_basic'

        run_cli(MODULE, config_ref, '-e', 'test', '-o', 'csv')

        files = _result_files(sid, 'config_basic')
        assert os.path.isfile(files['results']), (
            f"Expected results file not found: {files['results']}"
        )

    def test_config_set_runs_all(self, e2e_test_data, imported_distance_data_all, imported_configs):
        """Running the whole config set with -o csv produces result files for all configs.

        Args:
            e2e_test_data: Session-scoped test data dict.
            imported_distance_data_all: Ensures all distance data is in the DB.
            imported_configs: Ensures all configs are in the DB.
        """
        sid = e2e_test_data['sid']

        run_cli(MODULE, sid, '-e', 'test', '-o', 'csv')

        # Verify result files exist for at least the basic config variant.
        files = _result_files(sid, 'config_basic')
        assert os.path.isfile(files['results']), (
            f"Expected results file for config_basic not found: {files['results']}"
        )

        # Verify the result directory itself was created.
        rdir = _result_dir(sid)
        assert os.path.isdir(rdir), (
            f"Expected results directory to exist after config-set run: {rdir}"
        )

    def test_verbose_output(self, e2e_test_data, imported_distance_data_all, imported_configs):
        """Running with -v produces non-empty stdout output.

        Args:
            e2e_test_data: Session-scoped test data dict.
            imported_distance_data_all: Ensures all distance data is in the DB.
            imported_configs: Ensures all configs are in the DB.
        """
        sid = e2e_test_data['sid']
        config_ref = f'{sid}/{sid}_config_basic'

        result = run_cli(MODULE, config_ref, '-e', 'test', '-o', 'csv', '-v')

        assert result.stdout.strip(), 'Expected non-empty stdout with -v flag'

    def test_driving_time_config_solves(self, e2e_test_data, imported_distance_data_all, imported_configs):
        """A driving_time config loaded from the DB solves and writes a result file.

        Args:
            e2e_test_data: Session-scoped test data dict.
            imported_distance_data_all: Ensures all distance data (incl. duration) is in the DB.
            imported_configs: Ensures all configs (incl. metric) are in the DB.
        """
        sid = e2e_test_data['sid']
        config_ref = f'{sid}/{sid}_config_driving_duration'

        run_cli(MODULE, config_ref, '-e', 'test', '-o', 'csv')

        files = _result_files(sid, 'config_driving_duration')
        assert os.path.isfile(files['results']), (
            f"Expected driving_time results file not found: {files['results']}"
        )


# ---------------------------------------------------------------------------
# Class: TestModelRunDbCliDbOutput — DB output tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.e2e_db
class TestModelRunDbCliDbOutput:
    """Tests verifying that model_run_db_cli writes results to the database."""

    def test_single_config_db_output(
        self,
        e2e_test_data,
        imported_distance_data_all,
        imported_configs,
        test_environment,
    ):
        """Running a single config with -o db creates a ModelRun record in the DB.

        Args:
            e2e_test_data: Session-scoped test data dict.
            imported_distance_data_all: Ensures all distance data is in the DB.
            imported_configs: Ensures all configs are in the DB.
            test_environment: The loaded test environment; skips if not configured.
        """
        # Import lazily to avoid pulling in DB dependencies at collection time.
        from python.database.query import Query  # pylint: disable=import-outside-toplevel
        from python.database import models  # pylint: disable=import-outside-toplevel

        sid = e2e_test_data['sid']
        config_name = f'{sid}_config_basic'
        config_ref = f'{sid}/{config_name}'

        run_cli(MODULE, config_ref, '-e', 'test', '-o', 'db')

        query = Query(test_environment)

        # Confirm the ModelConfig record exists.
        db_config = query.find_model_configs_by_config_set_and_config_name(sid, config_name)
        assert db_config is not None, (
            f"No ModelConfig found for config_set='{sid}', config_name='{config_name}'"
        )

        # Confirm exactly one ModelRun was created for this config.  A single
        # `model_run_db_cli` invocation against a single config writes exactly
        # one ModelRun row; nothing else in this test session writes ModelRuns
        # for this config_name (the CSV-output tests use -o csv; other test
        # files don't go through model_run_db_cli at all), so a count != 1
        # would be a real bug we want surfaced.
        session = query.get_session()
        run_rows = (
            session.query(models.ModelRun)
            .filter(models.ModelRun.model_config_id == db_config.id)
            .all()
        )
        assert len(run_rows) == 1, (
            f"Expected exactly one ModelRun record for config_set='{sid}', "
            f"config_name='{config_name}', but found {len(run_rows)}."
        )
