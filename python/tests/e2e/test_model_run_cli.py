"""End-to-end tests for the CSV-based model run CLI (model_run_cli).

These tests exercise the full pipeline from config YAML files on disk through
the KP optimisation solver to the four output CSV files written per run.
"""

# pylint: disable=redefined-outer-name

import os
import shutil

import pandas as pd
import pytest

from python.tests.e2e.conftest import run_cli
from python.utils.directory_constants import RESULTS_BASE_DIR

MODULE = 'python.scripts.model_run_cli'

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

    The file naming convention is:
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
def cleanup_results(e2e_session_id):
    """Remove the session's result directory after all tests in this module.

    Args:
        e2e_session_id: The session identifier fixture.

    Yields:
        None
    """
    yield
    rdir = _result_dir(e2e_session_id)
    if os.path.isdir(rdir):
        shutil.rmtree(rdir)


# ---------------------------------------------------------------------------
# Helper: ensure a config has been run
# ---------------------------------------------------------------------------


def _ensure_run(e2e_test_data: dict, config_suffix: str) -> None:
    """Run the CLI for *config_suffix* if result files are not yet present.

    Args:
        e2e_test_data: The session-scoped test data dict from :func:`e2e_test_data`.
        config_suffix: The config variant key to run.
    """
    sid = e2e_test_data['sid']
    files = _result_files(sid, config_suffix)
    if not os.path.isfile(files['results']):
        config_path = e2e_test_data['configs'][config_suffix]
        run_cli(MODULE, config_path)


# ---------------------------------------------------------------------------
# Class: TestModelRunCliBasic — smoke tests
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.e2e_csv
class TestModelRunCliBasic:
    """Smoke tests verifying the CLI runs successfully and writes output files."""

    def test_single_config_basic(self, e2e_test_data):
        """Running config_basic produces all four expected output CSV files.

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        sid = e2e_test_data['sid']
        config_path = e2e_test_data['configs']['config_basic']

        run_cli(MODULE, config_path)

        files = _result_files(sid, 'config_basic')
        for file_type, path in files.items():
            assert os.path.isfile(path), (
                f"Expected {file_type} output file not found: {path}"
            )

    def test_multiple_configs(self, e2e_test_data):
        """Running config_low_beta and config_capacity in one invocation both succeed.

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        sid = e2e_test_data['sid']
        low_beta_path = e2e_test_data['configs']['config_low_beta']
        capacity_path = e2e_test_data['configs']['config_capacity']

        run_cli(MODULE, low_beta_path, capacity_path)

        for suffix in ('config_low_beta', 'config_capacity'):
            files = _result_files(sid, suffix)
            assert os.path.isfile(files['results']), (
                f"Results file missing for {suffix}: {files['results']}"
            )

    def test_concurrent_runs(self, e2e_test_data):
        """config_constrained runs successfully with -c 2.

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        sid = e2e_test_data['sid']
        config_path = e2e_test_data['configs']['config_constrained']

        run_cli(MODULE, config_path, '-c', '2')

        files = _result_files(sid, 'config_constrained')
        assert os.path.isfile(files['results']), (
            f"Results file missing after concurrent run: {files['results']}"
        )

    def test_verbose_logging(self, e2e_test_data):
        """Running with -vv produces non-empty stdout output.

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        config_path = e2e_test_data['configs']['config_basic']

        result = run_cli(MODULE, config_path, '-vv')

        assert result.stdout.strip(), 'Expected non-empty stdout with -vv flag'

    def test_custom_log_dir(self, e2e_test_data, tmp_path):
        """Running with -L <tmp_path> creates the specified log directory.

        Args:
            e2e_test_data: Session-scoped test data dict.
            tmp_path: pytest-provided temporary directory.
        """
        config_path = e2e_test_data['configs']['config_basic']
        custom_log_dir = str(tmp_path / 'custom_logs')

        run_cli(MODULE, config_path, '-L', custom_log_dir)

        assert os.path.isdir(custom_log_dir), (
            f"Custom log directory was not created: {custom_log_dir}"
        )


# ---------------------------------------------------------------------------
# Class: TestModelRunCliVariants — config variations
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.e2e_csv
class TestModelRunCliVariants:
    """Tests that each config variant runs end-to-end without error."""

    def test_driving_config(self, e2e_test_data):
        """config_driving runs successfully and produces result files.

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        sid = e2e_test_data['sid']
        config_path = e2e_test_data['configs']['config_driving']

        run_cli(MODULE, config_path)

        files = _result_files(sid, 'config_driving')
        assert os.path.isfile(files['results']), (
            f"Results file missing for config_driving: {files['results']}"
        )

    def test_log_config(self, e2e_test_data):
        """config_log runs successfully and produces result files.

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        sid = e2e_test_data['sid']
        config_path = e2e_test_data['configs']['config_log']

        run_cli(MODULE, config_path)

        files = _result_files(sid, 'config_log')
        assert os.path.isfile(files['results']), (
            f"Results file missing for config_log: {files['results']}"
        )

    def test_driving_log_config(self, e2e_test_data):
        """config_driving_log runs successfully and produces result files.

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        sid = e2e_test_data['sid']
        config_path = e2e_test_data['configs']['config_driving_log']

        run_cli(MODULE, config_path)

        files = _result_files(sid, 'config_driving_log')
        assert os.path.isfile(files['results']), (
            f"Results file missing for config_driving_log: {files['results']}"
        )

    def test_penalty_config(self, e2e_test_data):
        """config_penalty runs successfully and produces result files.

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        sid = e2e_test_data['sid']
        config_path = e2e_test_data['configs']['config_penalty']

        run_cli(MODULE, config_path)

        files = _result_files(sid, 'config_penalty')
        assert os.path.isfile(files['results']), (
            f"Results file missing for config_penalty: {files['results']}"
        )


# ---------------------------------------------------------------------------
# Class: TestModelRunCliValueAssertions — value-level checks
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.e2e_csv
class TestModelRunCliValueAssertions:
    """Value-level assertions on result CSV content produced by model_run_cli."""

    def test_results_columns(self, e2e_test_data):
        """The results CSV must contain id_orig, id_dest, and distance_m columns.

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        _ensure_run(e2e_test_data, 'config_basic')
        sid = e2e_test_data['sid']
        results_path = _result_files(sid, 'config_basic')['results']

        df = pd.read_csv(results_path)
        for col in ('id_orig', 'id_dest', 'distance_m'):
            assert col in df.columns, f"Expected column '{col}' in results CSV"

    def test_all_residences_assigned(self, e2e_test_data):
        """Every id_orig in the results must be a valid residence from the distances file.

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        _ensure_run(e2e_test_data, 'config_basic')
        sid = e2e_test_data['sid']
        results_path = _result_files(sid, 'config_basic')['results']

        results_df = pd.read_csv(results_path)
        distances_df = pd.read_csv(e2e_test_data['distances'])

        source_ids = set(distances_df['id_orig'].astype(str))
        result_ids = set(results_df['id_orig'].astype(str))

        assert result_ids.issubset(source_ids), (
            f"Result id_origs not a subset of source distances: "
            f"{result_ids - source_ids}"
        )

    def test_no_duplicate_assignments(self, e2e_test_data):
        """Each residence (id_orig) must appear at most once in the results.

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        _ensure_run(e2e_test_data, 'config_basic')
        sid = e2e_test_data['sid']
        results_path = _result_files(sid, 'config_basic')['results']

        df = pd.read_csv(results_path)
        duplicates = df[df.duplicated(subset=['id_orig'], keep=False)]
        assert duplicates.empty, (
            f"Duplicate id_orig entries found in results: "
            f"{duplicates['id_orig'].tolist()}"
        )

    def test_precincts_open_count(self, e2e_test_data):
        """The number of unique open precincts must not exceed precincts_open (3).

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        _ensure_run(e2e_test_data, 'config_basic')
        sid = e2e_test_data['sid']
        results_path = _result_files(sid, 'config_basic')['results']

        df = pd.read_csv(results_path)
        unique_precincts = df['id_dest'].nunique()
        assert unique_precincts <= 3, (
            f"Expected at most 3 open precincts, got {unique_precincts}"
        )

    def test_ede_demographics_present_and_positive(self, e2e_test_data):
        """The EDE file must have at least one row and positive y_EDE values.

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        _ensure_run(e2e_test_data, 'config_basic')
        sid = e2e_test_data['sid']
        edes_path = _result_files(sid, 'config_basic')['edes']

        df = pd.read_csv(edes_path)
        assert len(df) > 0, 'EDE file must have at least one row'
        assert 'y_EDE' in df.columns, 'EDE file must have a y_EDE column'
        assert (df['y_EDE'] > 0).all(), (
            f"All y_EDE values must be positive; found non-positive: "
            f"{df[df['y_EDE'] <= 0]['y_EDE'].tolist()}"
        )

    def test_residence_distances_count(self, e2e_test_data):
        """The residence distances file must contain at least one row.

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        _ensure_run(e2e_test_data, 'config_basic')
        sid = e2e_test_data['sid']
        res_path = _result_files(sid, 'config_basic')['residence_distances']

        df = pd.read_csv(res_path)
        assert len(df) > 0, 'Residence distances file must have at least one row'

    def test_precinct_distances_count(self, e2e_test_data):
        """The precinct distances file must contain at least one row.

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        _ensure_run(e2e_test_data, 'config_basic')
        sid = e2e_test_data['sid']
        prec_path = _result_files(sid, 'config_basic')['precinct_distances']

        df = pd.read_csv(prec_path)
        assert len(df) > 0, 'Precinct distances file must have at least one row'

    def test_capacity_constraint(self, e2e_test_data):
        """With capacity=3, no precinct exceeds ~3× the average assignment count.

        The config_capacity variant sets capacity=3, which caps how many residences
        can be assigned to each open polling location relative to the average.

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        _ensure_run(e2e_test_data, 'config_capacity')
        sid = e2e_test_data['sid']
        results_path = _result_files(sid, 'config_capacity')['results']

        df = pd.read_csv(results_path)
        assignments_per_precinct = df.groupby('id_dest').size()
        avg_assignments = assignments_per_precinct.mean()
        max_assignments = assignments_per_precinct.max()

        # Capacity=3 means max should not exceed 3× average
        assert max_assignments <= avg_assignments * 3, (
            f"Max assignments ({max_assignments}) exceeds 3× average "
            f"({avg_assignments * 3:.1f}) — capacity constraint may not be enforced"
        )

    def test_penalty_config_produces_valid_results(self, e2e_test_data):
        """The penalty config produces complete, non-empty result files.

        Penalised sites are discouraged by the KP scoring algorithm but are not
        hard-excluded, so they may still appear in the output.  This test
        verifies that the penalty pipeline runs end-to-end and writes valid CSV
        output rather than asserting that penalised sites are absent.

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        _ensure_run(e2e_test_data, 'config_penalty')
        sid = e2e_test_data['sid']
        files = _result_files(sid, 'config_penalty')

        results_df = pd.read_csv(files['results'])
        edes_df = pd.read_csv(files['edes'])

        assert len(results_df) > 0, 'Penalty config results must have at least one row'
        assert len(edes_df) > 0, 'Penalty config EDE output must have at least one row'

        for col in ('id_orig', 'id_dest', 'distance_m'):
            assert col in results_df.columns, (
                f"Expected column '{col}' in penalty results CSV"
            )

    def test_low_beta_differs_from_basic(self, e2e_test_data):
        """Different beta values should produce different EDE values.

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        _ensure_run(e2e_test_data, 'config_basic')
        _ensure_run(e2e_test_data, 'config_low_beta')
        sid = e2e_test_data['sid']

        basic_edes = pd.read_csv(_result_files(sid, 'config_basic')['edes'])
        low_beta_edes = pd.read_csv(_result_files(sid, 'config_low_beta')['edes'])

        # Sort by demographic to align rows before comparison
        basic_sorted = basic_edes.sort_values('demographic')['y_EDE'].reset_index(drop=True)
        low_beta_sorted = low_beta_edes.sort_values('demographic')['y_EDE'].reset_index(drop=True)

        # At least one y_EDE value must differ between the two configs
        assert not basic_sorted.equals(low_beta_sorted), (
            'Expected different EDE values for beta=-1 vs beta=-2, but they are identical'
        )

    def test_driving_differs_from_basic(self, e2e_test_data):
        """Driving distances should produce different distance_m values than haversine.

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        _ensure_run(e2e_test_data, 'config_basic')
        _ensure_run(e2e_test_data, 'config_driving')
        sid = e2e_test_data['sid']

        basic_df = pd.read_csv(_result_files(sid, 'config_basic')['results'])
        driving_df = pd.read_csv(_result_files(sid, 'config_driving')['results'])

        # Align on id_orig for comparison
        basic_merged = basic_df[['id_orig', 'distance_m']].set_index('id_orig').sort_index()
        driving_merged = driving_df[['id_orig', 'distance_m']].set_index('id_orig').sort_index()

        common_ids = basic_merged.index.intersection(driving_merged.index)
        assert len(common_ids) > 0, 'No common id_orig between basic and driving results'

        basic_distances = basic_merged.loc[common_ids, 'distance_m']
        driving_distances = driving_merged.loc[common_ids, 'distance_m']

        assert not basic_distances.equals(driving_distances), (
            'Expected driving distances to differ from haversine distances, but they are identical'
        )

    def test_log_differs_from_basic(self, e2e_test_data):
        """Log distance transform should produce different EDE values than linear.

        Args:
            e2e_test_data: Session-scoped test data dict.
        """
        _ensure_run(e2e_test_data, 'config_basic')
        _ensure_run(e2e_test_data, 'config_log')
        sid = e2e_test_data['sid']

        basic_edes = pd.read_csv(_result_files(sid, 'config_basic')['edes'])
        log_edes = pd.read_csv(_result_files(sid, 'config_log')['edes'])

        basic_sorted = basic_edes.sort_values('demographic')['y_EDE'].reset_index(drop=True)
        log_sorted = log_edes.sort_values('demographic')['y_EDE'].reset_index(drop=True)

        assert not basic_sorted.equals(log_sorted), (
            'Expected different EDE values for log vs linear distances, but they are identical'
        )
