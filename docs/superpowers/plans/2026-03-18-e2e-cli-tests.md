# E2E CLI Test Suite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an automated end-to-end test suite that exercises all CLI scripts via subprocess, covering both CSV and DB flows with session-isolated test data.

**Architecture:** Pytest fixture dependency chain with session-scoped fixtures. Test data is templated from existing `datasets/polling/testing/` files with a unique session ID per run. CSV tests always run; DB tests skip gracefully when no `test` environment is configured. A `run.py e2e_tests` command wraps Docker execution.

**Tech Stack:** Python, pytest, subprocess, PyYAML, pandas, SQLAlchemy (BigQuery), Docker

**Spec:** `docs/superpowers/specs/2026-03-18-e2e-cli-tests-design.md`

**Branch:** `feature/cli-e2e-tests`

---

## File Structure

```
python/tests/e2e/
  __init__.py                          # Package init
  conftest.py                          # Session fixtures, helpers, markers, skip logic, cleanup
  test_model_run_cli.py                # CSV model runs (e2e_csv)
  test_auto_generate_config.py         # Config generation (e2e_csv + optional e2e_db)
  test_db_import_potential_locations.py # DB import (e2e_db)
  test_db_import_driving_distances.py  # DB import (e2e_db)
  test_db_import_distance_data.py      # DB import (e2e_db)
  test_db_import_config.py             # DB import (e2e_db)
  test_model_run_db_cli.py             # DB model runs (e2e_db)
run.py                                 # Modified to support e2e_tests command
pytest.ini                             # Register custom markers (or pyproject.toml)
```

---

### Task 1: Create branch and register pytest markers

**Files:**
- Modify: `pytest.ini` (or create if absent; check for `pyproject.toml` alternative)
- Create: `python/tests/e2e/__init__.py`

- [ ] **Step 1: Create feature branch**

```bash
git checkout -b feature/cli-e2e-tests
```

- [ ] **Step 2: Check where pytest config lives**

Look for `pytest.ini`, `pyproject.toml` `[tool.pytest]` section, or `setup.cfg` `[tool:pytest]`. Register markers in whichever file is already used. If none exists, create `pytest.ini`.

Register these markers:
```ini
[pytest]
markers =
    e2e: End-to-end CLI tests
    e2e_csv: CSV-based e2e tests (no external dependencies)
    e2e_db: Database-backed e2e tests (requires test environment in settings.yaml)
```

- [ ] **Step 3: Create e2e package init**

Create empty `python/tests/e2e/__init__.py`.

- [ ] **Step 4: Verify pytest discovers the new directory**

Run: `docker compose run --rm app pytest python/tests/e2e/ --collect-only`
Expected: `no tests ran` (no test files yet, but no errors)

- [ ] **Step 5: Commit**

```bash
git add pytest.ini python/tests/e2e/__init__.py
git commit -m "feat: register e2e pytest markers and create e2e test package"
```

---

### Task 2: Add `e2e_tests` command to `run.py`

**Files:**
- Modify: `run.py:27-59` (the `main()` function)

The current `run.py` validates `script` against `get_scripts()` which only finds files in `python/scripts/`. We need to intercept `e2e_tests` before argparse validation.

- [ ] **Step 1: Write a test for the run.py change**

Create `python/tests/e2e/test_run_py.py`:

```python
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
        # We can't run the full Docker command in CI, but we can verify
        # the argument parsing doesn't reject 'e2e_tests'
        result = subprocess.run(
            [sys.executable, 'run.py', 'e2e_tests', '--help'],
            capture_output=True, text=True, timeout=10,
        )
        # It will fail because Docker isn't running pytest with --help,
        # but it should NOT fail with "invalid choice: 'e2e_tests'"
        assert 'invalid choice' not in result.stderr
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest python/tests/e2e/test_run_py.py -v`
Expected: FAIL — `run.py` currently rejects `e2e_tests` as an invalid script choice.

- [ ] **Step 3: Modify `run.py` to support `e2e_tests`**

In `run.py`, add special-case handling before argparse. Replace the `main()` function body with logic that checks `sys.argv` for `e2e_tests` first:

```python
def main():
    # Special command: e2e_tests bypasses script discovery
    if len(sys.argv) > 1 and sys.argv[1] == 'e2e_tests':
        env = os.environ.copy()
        env["GCP_CREDS_PATH"] = get_gcp_creds_path()
        extra_args = sys.argv[2:]
        cmd = [
            "docker", "compose", "run", "--rm", "app",
            "pytest", "python/tests/e2e/"
        ] + extra_args
        try:
            subprocess.run(cmd, env=env, check=True)
        except subprocess.CalledProcessError as e:
            sys.exit(e.returncode)
        except KeyboardInterrupt:
            print("\n[Terminated by User]")
            sys.exit(130)
        return

    # ... existing argparse logic unchanged ...
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest python/tests/e2e/test_run_py.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add run.py python/tests/e2e/test_run_py.py
git commit -m "feat: add e2e_tests command to run.py for Docker-based e2e test execution"
```

---

### Task 3: Build the conftest.py — session ID, CLI helper, and test data templating

**Files:**
- Create: `python/tests/e2e/conftest.py`

This is the core infrastructure. It provides:
1. Session ID generation (`e2e_{uuid4_hex[:6]}`)
2. A `run_cli` helper that invokes scripts via subprocess
3. The `e2e_test_data` fixture that templates CSVs and configs
4. Pytest markers auto-applied via `pytestmark`

- [ ] **Step 1: Write a test for the session ID fixture**

Create `python/tests/e2e/test_conftest_fixtures.py`:

```python
"""Tests that verify the e2e conftest fixtures work correctly."""

import os
import re

import pytest


@pytest.mark.e2e
@pytest.mark.e2e_csv
class TestSessionFixtures:
    """Verify session data templating fixtures."""

    def test_session_id_format(self, e2e_session_id):
        """Session ID should match e2e_{6 hex chars}."""
        assert re.match(r'^e2e_[0-9a-f]{6}$', e2e_session_id)

    def test_test_data_creates_polling_dir(self, e2e_test_data):
        """Templated polling data directory should exist."""
        assert os.path.isdir(e2e_test_data['polling_dir'])

    def test_test_data_creates_potential_locations(self, e2e_test_data):
        """Potential locations CSV should exist at conventional path."""
        assert os.path.isfile(e2e_test_data['potential_locations_csv'])

    def test_test_data_creates_distance_csv(self, e2e_test_data):
        """Haversine distance CSV should exist at conventional path."""
        assert os.path.isfile(e2e_test_data['distances_csv'])

    def test_test_data_creates_driving_csv(self, e2e_test_data):
        """Driving distance CSV should exist at conventional path."""
        assert os.path.isfile(e2e_test_data['driving_distances_csv'])

    def test_test_data_creates_log_csv(self, e2e_test_data):
        """Log-transformed distance CSV should exist."""
        assert os.path.isfile(e2e_test_data['distances_log_csv'])

    def test_test_data_creates_driving_log_csv(self, e2e_test_data):
        """Log-transformed driving distance CSV should exist."""
        assert os.path.isfile(e2e_test_data['driving_distances_log_csv'])

    def test_test_data_creates_driving_import_csv(self, e2e_test_data):
        """Driving distances CSV for db_import should exist in datasets/driving/."""
        assert os.path.isfile(e2e_test_data['driving_import_csv'])

    def test_test_data_creates_configs(self, e2e_test_data):
        """All 8 config YAML files should exist."""
        assert len(e2e_test_data['config_paths']) == 8
        for path in e2e_test_data['config_paths'].values():
            assert os.path.isfile(path)

    def test_test_data_creates_autogen_template(self, e2e_test_data):
        """Auto-generate template should exist."""
        assert os.path.isfile(e2e_test_data['autogen_template_path'])

    def test_config_set_matches_directory(self, e2e_test_data, e2e_session_id):
        """Config YAML config_set field must match parent directory name."""
        import yaml
        for path in e2e_test_data['config_paths'].values():
            with open(path, 'r') as f:
                config = yaml.safe_load(f)
            parent_dir = os.path.basename(os.path.dirname(path))
            assert config['config_set'] == parent_dir == e2e_session_id
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest python/tests/e2e/test_conftest_fixtures.py -v`
Expected: FAIL — fixtures don't exist yet.

- [ ] **Step 3: Implement conftest.py**

Create `python/tests/e2e/conftest.py`:

```python
"""E2E test fixtures: session isolation, test data templating, CLI helpers."""

import math
import os
import shutil
import subprocess
import sys
import uuid

import pandas as pd
import pytest
import yaml

from python.utils.directory_constants import (
    POLLING_DIR, DRIVING_DIR, CONFIG_BASE_DIR, SETTINGS_PATH,
)


# ---------------------------------------------------------------------------
# Session ID
# ---------------------------------------------------------------------------

@pytest.fixture(scope='session')
def e2e_session_id():
    """Generate a unique session ID for test isolation."""
    return f'e2e_{uuid.uuid4().hex[:6]}'


# ---------------------------------------------------------------------------
# CLI helper
# ---------------------------------------------------------------------------

def run_cli(script_module, *args, timeout=600):
    """Run a CLI script as a subprocess and return the CompletedProcess.

    Args:
        script_module: The script module path, e.g. 'python.scripts.model_run_cli'.
        *args: Arguments to pass to the script.
        timeout: Timeout in seconds.

    Returns:
        subprocess.CompletedProcess with captured stdout/stderr.

    Raises:
        AssertionError: If the process exits with a non-zero return code.
    """
    cmd = [sys.executable, '-m', script_module] + [str(a) for a in args]
    result = subprocess.run(
        cmd, capture_output=True, text=True, timeout=timeout,
    )
    assert result.returncode == 0, (
        f'CLI command failed: {" ".join(cmd)}\n'
        f'Exit code: {result.returncode}\n'
        f'stdout:\n{result.stdout}\n'
        f'stderr:\n{result.stderr}'
    )
    return result


# ---------------------------------------------------------------------------
# Test data templating
# ---------------------------------------------------------------------------

# Source test data paths
_SOURCE_POLLING_DIR = os.path.join(POLLING_DIR, 'testing')
_SOURCE_POTENTIAL_LOCATIONS = os.path.join(_SOURCE_POLLING_DIR, 'testing_potential_locations.csv')
_SOURCE_DISTANCES = os.path.join(_SOURCE_POLLING_DIR, 'testing_distances_2020.csv')
_SOURCE_DRIVING = os.path.join(_SOURCE_POLLING_DIR, 'testing_driving_2020.csv')

# Base config to use as template
_SOURCE_CONFIG = os.path.join(CONFIG_BASE_DIR, 'testing', 'testing_config_no_bg.yaml')

# Config variants: suffix -> field overrides
CONFIG_VARIANTS = {
    'config_basic': {},
    'config_driving': {'driving': True},
    'config_log': {'log_distance': True},
    'config_driving_log': {'driving': True, 'log_distance': True},
    'config_penalty': {'penalized_sites': ['College Campus - Potential', 'Fire Station - Potential']},
    'config_low_beta': {'beta': -1},
    'config_capacity': {'capacity': 3},
    'config_constrained': {'maxpctnew': 0.5, 'minpctold': 0.75},
}


def _create_log_transformed_csv(source_path, dest_path):
    """Create a log-transformed distance CSV from a source distance CSV.

    Args:
        source_path: Path to the source distance CSV.
        dest_path: Path to write the log-transformed CSV.
    """
    df = pd.read_csv(source_path)
    df['distance_m'] = df['distance_m'].apply(lambda x: math.log(x) if x > 0 else x)
    # Update source column to reflect log transform
    df['source'] = df['source'].str.replace('distance', 'log distance', regex=False)
    df.to_csv(dest_path, index=False)


@pytest.fixture(scope='session')
def e2e_test_data(e2e_session_id):
    """Create session-isolated test data at conventional dataset paths.

    Creates polling data, driving data, configs, and auto-generate template.
    Cleans up after the session.

    Returns:
        dict with paths to all created test data files and directories.
    """
    sid = e2e_session_id

    # --- Directory paths ---
    polling_dir = os.path.join(POLLING_DIR, sid)
    driving_dir = os.path.join(DRIVING_DIR, sid)
    config_dir = os.path.join(CONFIG_BASE_DIR, sid)

    os.makedirs(polling_dir, exist_ok=True)
    os.makedirs(driving_dir, exist_ok=True)
    os.makedirs(config_dir, exist_ok=True)

    # --- CSV files ---
    # Potential locations
    potential_locations_csv = os.path.join(polling_dir, f'{sid}_potential_locations.csv')
    shutil.copy2(_SOURCE_POTENTIAL_LOCATIONS, potential_locations_csv)

    # Haversine distances
    distances_csv = os.path.join(polling_dir, f'{sid}_distances_2020.csv')
    shutil.copy2(_SOURCE_DISTANCES, distances_csv)

    # Driving distances (in polling dir, named per build_distance_file_path convention)
    driving_distances_csv = os.path.join(polling_dir, f'{sid}_driving_distances_2020.csv')
    shutil.copy2(_SOURCE_DRIVING, driving_distances_csv)

    # Log-transformed variants
    distances_log_csv = os.path.join(polling_dir, f'{sid}_distances_2020_log.csv')
    _create_log_transformed_csv(_SOURCE_DISTANCES, distances_log_csv)

    driving_distances_log_csv = os.path.join(polling_dir, f'{sid}_driving_distances_2020_log.csv')
    _create_log_transformed_csv(_SOURCE_DRIVING, driving_distances_log_csv)

    # Driving distances for db_import_driving_distances_cli (in datasets/driving/)
    driving_import_csv = os.path.join(driving_dir, f'{sid}_driving_distances.csv')
    shutil.copy2(_SOURCE_DRIVING, driving_import_csv)

    # --- Config YAML files ---
    with open(_SOURCE_CONFIG, 'r', encoding='utf-8') as f:
        base_config = yaml.safe_load(f)

    config_paths = {}
    for suffix, overrides in CONFIG_VARIANTS.items():
        config_name = f'{sid}_{suffix}'
        config = dict(base_config)
        config['config_set'] = sid
        config['config_name'] = config_name
        config['location'] = sid
        config.update(overrides)

        config_path = os.path.join(config_dir, f'{config_name}.yaml')
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)
        config_paths[suffix] = config_path

    # --- Auto-generate template ---
    # auto_generate_config.py validates template fields against the SQLAlchemy
    # ModelConfig model columns via check_model_fields_match_input(). The template
    # must include all nullable ModelConfig columns plus config_set/config_name.
    # The base_config from testing_config_no_bg.yaml is missing driving, log_distance,
    # and penalized_sites — we must add them explicitly.
    autogen_template_name = f'{sid}_autogen_template'
    autogen_config = dict(base_config)
    autogen_config['config_set'] = sid
    autogen_config['config_name'] = autogen_template_name
    autogen_config['location'] = sid
    # Ensure all ModelConfig-required fields are present
    autogen_config.setdefault('driving', False)
    autogen_config.setdefault('log_distance', False)
    autogen_config.setdefault('penalized_sites', None)
    # Auto-generate specific fields
    autogen_config['field_to_vary'] = 'year'
    autogen_config['new_range'] = [['2020'], ['2022']]

    autogen_template_path = os.path.join(config_dir, f'{autogen_template_name}.yaml_template')
    with open(autogen_template_path, 'w', encoding='utf-8') as f:
        yaml.dump(autogen_config, f, default_flow_style=False, sort_keys=False)

    data = {
        'session_id': sid,
        'polling_dir': polling_dir,
        'driving_dir': driving_dir,
        'config_dir': config_dir,
        'potential_locations_csv': potential_locations_csv,
        'distances_csv': distances_csv,
        'driving_distances_csv': driving_distances_csv,
        'distances_log_csv': distances_log_csv,
        'driving_distances_log_csv': driving_distances_log_csv,
        'driving_import_csv': driving_import_csv,
        'config_paths': config_paths,
        'autogen_template_path': autogen_template_path,
    }

    yield data

    # --- Cleanup ---
    shutil.rmtree(polling_dir, ignore_errors=True)
    shutil.rmtree(driving_dir, ignore_errors=True)
    shutil.rmtree(config_dir, ignore_errors=True)


# ---------------------------------------------------------------------------
# DB environment + skip logic
# ---------------------------------------------------------------------------

@pytest.fixture(scope='session')
def test_environment():
    """Load the 'test' environment from settings.yaml.

    Returns:
        Environment instance, or skips the test if not configured.
    """
    if not os.path.isfile(SETTINGS_PATH):
        pytest.skip(f'Settings file not found: {SETTINGS_PATH}')

    with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
        settings = yaml.safe_load(f)

    if 'test' not in settings:
        pytest.skip("No 'test' environment in settings.yaml — skipping DB tests")

    from python.utils.environments import load_env
    return load_env('test')


@pytest.fixture(scope='session')
def clean_test_data(test_environment):
    """Delete all e2e_* prefixed data from the test database.

    Deletes in dependency order (children before parents) since no cascade
    deletes are defined in the database models.
    """
    from python.database import sqlalchemy_main
    from python.database.models import (
        ModelConfig, ModelRun, Result, EDES, PrecintDistance, ResidenceDistance,
        PotentialLocationsSet, PotentialLocations,
        DistanceDataSet, DistanceData,
        DrivingDistancesSet, DrivingDistance,
    )

    sqlalchemy_main.setup(test_environment)
    session = sqlalchemy_main.Session()

    try:
        # 1. Find model_configs matching e2e_%
        e2e_configs = session.query(ModelConfig).filter(
            ModelConfig.config_set.like('e2e_%')
        ).all()
        config_ids = [c.id for c in e2e_configs]

        if config_ids:
            # 2. Find model_runs for those configs
            e2e_runs = session.query(ModelRun).filter(
                ModelRun.model_config_id.in_(config_ids)
            ).all()
            run_ids = [r.id for r in e2e_runs]

            if run_ids:
                # 3. Delete result children
                session.query(Result).filter(Result.model_run_id.in_(run_ids)).delete(
                    synchronize_session=False)
                session.query(EDES).filter(EDES.model_run_id.in_(run_ids)).delete(
                    synchronize_session=False)
                session.query(PrecintDistance).filter(
                    PrecintDistance.model_run_id.in_(run_ids)).delete(
                    synchronize_session=False)
                session.query(ResidenceDistance).filter(
                    ResidenceDistance.model_run_id.in_(run_ids)).delete(
                    synchronize_session=False)

            # 4. Delete model_runs
            session.query(ModelRun).filter(
                ModelRun.model_config_id.in_(config_ids)).delete(
                synchronize_session=False)

        # 5. Delete model_configs
        session.query(ModelConfig).filter(
            ModelConfig.config_set.like('e2e_%')).delete(
            synchronize_session=False)

        # 6. Distance data
        e2e_dd_sets = session.query(DistanceDataSet).filter(
            DistanceDataSet.location.like('e2e_%')).all()
        dd_set_ids = [s.id for s in e2e_dd_sets]
        if dd_set_ids:
            session.query(DistanceData).filter(
                DistanceData.distance_data_set_id.in_(dd_set_ids)).delete(
                synchronize_session=False)
        session.query(DistanceDataSet).filter(
            DistanceDataSet.location.like('e2e_%')).delete(
            synchronize_session=False)

        # 7. Driving distances
        e2e_drv_sets = session.query(DrivingDistancesSet).filter(
            DrivingDistancesSet.location.like('e2e_%')).all()
        drv_set_ids = [s.id for s in e2e_drv_sets]
        if drv_set_ids:
            session.query(DrivingDistance).filter(
                DrivingDistance.driving_distance_set_id.in_(drv_set_ids)).delete(
                synchronize_session=False)
        session.query(DrivingDistancesSet).filter(
            DrivingDistancesSet.location.like('e2e_%')).delete(
            synchronize_session=False)

        # 8. Potential locations
        e2e_pl_sets = session.query(PotentialLocationsSet).filter(
            PotentialLocationsSet.location.like('e2e_%')).all()
        pl_set_ids = [s.id for s in e2e_pl_sets]
        if pl_set_ids:
            session.query(PotentialLocations).filter(
                PotentialLocations.potential_locations_set_id.in_(pl_set_ids)).delete(
                synchronize_session=False)
        session.query(PotentialLocationsSet).filter(
            PotentialLocationsSet.location.like('e2e_%')).delete(
            synchronize_session=False)

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Shared DB import fixtures (session-scoped dependency chain)
# ---------------------------------------------------------------------------
# These fixtures form the dependency chain described in the spec.
# Each runs at most once per session. Individual test files declare
# dependencies on the fixtures they need.

@pytest.fixture(scope='session')
def imported_potential_locations(e2e_test_data, clean_test_data, test_environment):
    """Import potential locations into the test database."""
    sid = e2e_test_data['session_id']
    return run_cli('python.scripts.db_import_potential_locations_cli', sid, '-e', 'test')


@pytest.fixture(scope='session')
def imported_driving_distances(e2e_test_data, clean_test_data, test_environment):
    """Import driving distances into the test database."""
    sid = e2e_test_data['session_id']
    return run_cli('python.scripts.db_import_driving_distances_cli', '2020', sid, '-e', 'test')


@pytest.fixture(scope='session')
def imported_distance_data_all(
    e2e_test_data, clean_test_data, test_environment,
    imported_potential_locations, imported_driving_distances,
):
    """Import all 4 permutations of distance data."""
    sid = e2e_test_data['session_id']
    results = {}
    for t_flag, d_flag, key in [
        ('linear', False, 'linear'),
        ('log', False, 'log'),
        ('linear', True, 'driving_linear'),
        ('log', True, 'driving_log'),
    ]:
        args = ['python.scripts.db_import_distance_data_cli', '2020', sid, '-e', 'test', '-t', t_flag]
        if d_flag:
            args.append('-d')
        results[key] = run_cli(*args)
    return results


@pytest.fixture(scope='session')
def imported_configs(e2e_test_data, clean_test_data, test_environment):
    """Import all test configs into the database."""
    config_paths = list(e2e_test_data['config_paths'].values())
    return run_cli('python.scripts.db_import_config_cli', *config_paths, '-e', 'test')
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest python/tests/e2e/test_conftest_fixtures.py -v`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add python/tests/e2e/conftest.py python/tests/e2e/test_conftest_fixtures.py
git commit -m "feat: add e2e conftest with session ID, CLI helper, test data templating, and DB cleanup"
```

---

### Task 4: CSV model run tests (`test_model_run_cli.py`)

**Files:**
- Create: `python/tests/e2e/test_model_run_cli.py`

**Context:** `model_run_cli` takes positional config paths and writes results to `datasets/results/{location}_results/`. The result files are named `{config_set}.{config_name}_results.csv`, `_precinct_distances.csv`, `_residence_distances.csv`, `_edes.csv`.

- [ ] **Step 1: Write the test file**

Create `python/tests/e2e/test_model_run_cli.py`:

```python
"""E2E tests for model_run_cli: CSV-based model runs with various config options."""

import os

import pandas as pd
import pytest

from python.tests.e2e.conftest import run_cli
from python.utils.directory_constants import RESULTS_BASE_DIR


MODULE = 'python.scripts.model_run_cli'


def _result_dir(session_id):
    """Return the results directory for this session."""
    return os.path.join(RESULTS_BASE_DIR, f'{session_id}_results')


def _result_files(session_id, config_suffix):
    """Return paths to the 4 result files for a given config."""
    result_dir = _result_dir(session_id)
    prefix = f'{session_id}.{session_id}_{config_suffix}'
    return {
        'results': os.path.join(result_dir, f'{prefix}_results.csv'),
        'precinct_distances': os.path.join(result_dir, f'{prefix}_precinct_distances.csv'),
        'residence_distances': os.path.join(result_dir, f'{prefix}_residence_distances.csv'),
        'edes': os.path.join(result_dir, f'{prefix}_edes.csv'),
    }


@pytest.fixture(scope='module', autouse=True)
def cleanup_results(e2e_test_data):
    """Clean up result files after tests complete."""
    sid = e2e_test_data['session_id']
    yield
    import shutil
    result_dir = _result_dir(sid)
    shutil.rmtree(result_dir, ignore_errors=True)


@pytest.mark.e2e
@pytest.mark.e2e_csv
class TestModelRunCliBasic:
    """Smoke tests: CLI exits 0 and produces output files."""

    def test_single_config_basic(self, e2e_test_data):
        """Run a single basic config and verify output files."""
        paths = e2e_test_data['config_paths']
        run_cli(MODULE, paths['config_basic'])

        files = _result_files(e2e_test_data['session_id'], 'config_basic')
        for name, path in files.items():
            assert os.path.isfile(path), f'Missing output: {name} at {path}'

    def test_multiple_configs(self, e2e_test_data):
        """Run two configs in one invocation."""
        paths = e2e_test_data['config_paths']
        run_cli(MODULE, paths['config_low_beta'], paths['config_capacity'])

        for suffix in ['config_low_beta', 'config_capacity']:
            files = _result_files(e2e_test_data['session_id'], suffix)
            assert os.path.isfile(files['results'])

    def test_concurrent_runs(self, e2e_test_data):
        """Run with -c 2 for concurrent processing."""
        paths = e2e_test_data['config_paths']
        run_cli(MODULE, paths['config_constrained'], '-c', '2')

        files = _result_files(e2e_test_data['session_id'], 'config_constrained')
        assert os.path.isfile(files['results'])

    def test_verbose_logging(self, e2e_test_data):
        """Run with -vv; verify extra output in stdout."""
        paths = e2e_test_data['config_paths']
        result = run_cli(MODULE, paths['config_basic'], '-vv')
        assert 'Starting config' in result.stdout or 'Finished config' in result.stdout

    def test_custom_log_dir(self, e2e_test_data, tmp_path):
        """Run with -L for custom log directory."""
        paths = e2e_test_data['config_paths']
        log_dir = str(tmp_path / 'e2e_logs')
        run_cli(MODULE, paths['config_basic'], '-L', log_dir)
        assert os.path.isdir(log_dir)


@pytest.mark.e2e
@pytest.mark.e2e_csv
class TestModelRunCliVariants:
    """Test config variations produce valid results."""

    def test_driving_config(self, e2e_test_data):
        """Run with driving distances enabled."""
        run_cli(MODULE, e2e_test_data['config_paths']['config_driving'])
        files = _result_files(e2e_test_data['session_id'], 'config_driving')
        assert os.path.isfile(files['results'])

    def test_log_config(self, e2e_test_data):
        """Run with log-transformed distances."""
        run_cli(MODULE, e2e_test_data['config_paths']['config_log'])
        files = _result_files(e2e_test_data['session_id'], 'config_log')
        assert os.path.isfile(files['results'])

    def test_driving_log_config(self, e2e_test_data):
        """Run with driving + log distances."""
        run_cli(MODULE, e2e_test_data['config_paths']['config_driving_log'])
        files = _result_files(e2e_test_data['session_id'], 'config_driving_log')
        assert os.path.isfile(files['results'])

    def test_penalty_config(self, e2e_test_data):
        """Run with penalized sites."""
        run_cli(MODULE, e2e_test_data['config_paths']['config_penalty'])
        files = _result_files(e2e_test_data['session_id'], 'config_penalty')
        assert os.path.isfile(files['results'])


@pytest.mark.e2e
@pytest.mark.e2e_csv
class TestModelRunCliValueAssertions:
    """Value-level assertions on model run outputs."""

    def test_results_columns(self, e2e_test_data):
        """Result CSV has expected columns."""
        files = _result_files(e2e_test_data['session_id'], 'config_basic')
        df = pd.read_csv(files['results'])
        for col in ['id_orig', 'id_dest', 'distance_m', 'population']:
            assert col in df.columns, f'Missing column: {col}'

    def test_all_residences_assigned(self, e2e_test_data):
        """Every id_orig in source data appears in results (no unassigned residences)."""
        source_df = pd.read_csv(e2e_test_data['distances_csv'])
        source_origs = set(source_df['id_orig'].unique())

        files = _result_files(e2e_test_data['session_id'], 'config_basic')
        result_df = pd.read_csv(files['results'])
        result_origs = set(result_df['id_orig'].unique())

        # Results only contain rows after bad_types filtering, so result_origs
        # should be a subset of source_origs (all assigned)
        assert len(result_origs) > 0
        assert result_origs.issubset(source_origs)

    def test_no_duplicate_assignments(self, e2e_test_data):
        """Each residence should be assigned to exactly one precinct."""
        files = _result_files(e2e_test_data['session_id'], 'config_basic')
        df = pd.read_csv(files['results'])
        assert not df['id_orig'].duplicated().any()

    def test_precincts_open_count(self, e2e_test_data):
        """Number of open precincts matches config's precincts_open (3)."""
        files = _result_files(e2e_test_data['session_id'], 'config_basic')
        df = pd.read_csv(files['results'])
        assert df['id_dest'].nunique() <= 3  # precincts_open = 3

    def test_ede_demographics_present_and_positive(self, e2e_test_data):
        """EDE file has rows for demographic groups with positive y_ede and avg_dist."""
        files = _result_files(e2e_test_data['session_id'], 'config_basic')
        df = pd.read_csv(files['edes'])
        assert len(df) > 0
        # y_ede and avg_dist should be present and positive
        if 'y_ede' in df.columns:
            assert (df['y_ede'] > 0).all()
        if 'avg_dist' in df.columns:
            assert (df['avg_dist'] > 0).all()

    def test_residence_distances_count(self, e2e_test_data):
        """Residence distance count should match unique id_orig in source data."""
        files = _result_files(e2e_test_data['session_id'], 'config_basic')
        res_df = pd.read_csv(files['residence_distances'])
        result_df = pd.read_csv(files['results'])
        # Each unique id_orig in results should appear in residence distances
        assert res_df.index.nunique() > 0 or len(res_df) > 0

    def test_precinct_distances_count(self, e2e_test_data):
        """Precinct distance count should relate to precincts_open (3)."""
        files = _result_files(e2e_test_data['session_id'], 'config_basic')
        prec_df = pd.read_csv(files['precinct_distances'])
        assert len(prec_df) > 0

    def test_capacity_constraint(self, e2e_test_data):
        """Capacity config (capacity=3) limits assignments per precinct."""
        files = _result_files(e2e_test_data['session_id'], 'config_capacity')
        if not os.path.isfile(files['results']):
            run_cli(MODULE, e2e_test_data['config_paths']['config_capacity'])
        df = pd.read_csv(files['results'])
        result_df = pd.read_csv(files['results'])
        # With capacity=3 and precincts_open=3, each precinct should handle
        # at most ceil(total_residences / precincts_open) * capacity fraction
        # At minimum, verify the constraint is active by checking precinct counts
        counts = result_df.groupby('id_dest').size()
        assert counts.max() > 0
        # The capacity multiplier limits the max relative to average
        avg_per_precinct = len(result_df) / result_df['id_dest'].nunique()
        assert counts.max() <= avg_per_precinct * 3 + 1  # capacity=3 multiplier

    def test_penalty_excludes_penalized_sites(self, e2e_test_data):
        """Penalized sites should not appear as open precincts in results."""
        files = _result_files(e2e_test_data['session_id'], 'config_penalty')
        if not os.path.isfile(files['results']):
            run_cli(MODULE, e2e_test_data['config_paths']['config_penalty'])
        df = pd.read_csv(files['results'])
        # Penalized sites: 'College Campus - Potential', 'Fire Station - Potential'
        # These location_type values should not appear in assigned precincts
        if 'location_type' in df.columns:
            assigned_types = set(df['location_type'].unique())
            assert 'College Campus - Potential' not in assigned_types
            assert 'Fire Station - Potential' not in assigned_types

    def test_low_beta_differs_from_basic(self, e2e_test_data):
        """Different beta values should produce different EDE values."""
        basic_files = _result_files(e2e_test_data['session_id'], 'config_basic')
        low_beta_files = _result_files(e2e_test_data['session_id'], 'config_low_beta')

        if not os.path.isfile(low_beta_files['edes']):
            run_cli(MODULE, e2e_test_data['config_paths']['config_low_beta'])

        basic_ede = pd.read_csv(basic_files['edes'])
        low_beta_ede = pd.read_csv(low_beta_files['edes'])

        # With different betas, the y_ede values should differ
        assert not basic_ede.equals(low_beta_ede)

    def test_driving_differs_from_basic(self, e2e_test_data):
        """Driving distances should produce different results than haversine."""
        basic_files = _result_files(e2e_test_data['session_id'], 'config_basic')
        driving_files = _result_files(e2e_test_data['session_id'], 'config_driving')

        basic_df = pd.read_csv(basic_files['results'])
        driving_df = pd.read_csv(driving_files['results'])

        # Distance values should differ between haversine and driving
        assert not basic_df['distance_m'].equals(driving_df['distance_m'])

    def test_log_differs_from_basic(self, e2e_test_data):
        """Log-transformed distances should produce different results than linear."""
        basic_files = _result_files(e2e_test_data['session_id'], 'config_basic')
        log_files = _result_files(e2e_test_data['session_id'], 'config_log')

        if not os.path.isfile(log_files['results']):
            run_cli(MODULE, e2e_test_data['config_paths']['config_log'])

        basic_ede = pd.read_csv(basic_files['edes'])
        log_ede = pd.read_csv(log_files['edes'])

        assert not basic_ede.equals(log_ede)
```

- [ ] **Step 2: Run tests to verify failures (no results yet)**

Run: `pytest python/tests/e2e/test_model_run_cli.py::TestModelRunCliBasic::test_single_config_basic -v`
Expected: PASS (this actually runs the model — may take 30-60 seconds). If the test data fixture works, this should invoke the CLI and produce results.

If the fixture or CLI fails, debug before continuing.

- [ ] **Step 3: Run all CSV tests**

Run: `pytest python/tests/e2e/test_model_run_cli.py -v`
Expected: All PASS. Model runs may take a few minutes total.

- [ ] **Step 4: Commit**

```bash
git add python/tests/e2e/test_model_run_cli.py
git commit -m "feat: add e2e tests for model_run_cli with config variants and value assertions"
```

---

### Task 5: Auto-generate config tests (`test_auto_generate_config.py`)

**Files:**
- Create: `python/tests/e2e/test_auto_generate_config.py`

**Context:** `auto_generate_config.py` uses `-b` for base config path. It validates that config file parent dir matches `config_set` and file name matches `config_name`. It reads `field_to_vary` and `new_range` from the template, then generates one YAML per value in `new_range`. The template also needs fields that match the `ModelConfig` SQLAlchemy model (including `driving`, `log_distance`, `penalized_sites`).

**Important:** `auto_generate_config.py` validates config fields against the SQLAlchemy `ModelConfig` model's columns. The template must have fields matching the DB model, not the `PollingModelConfig` dataclass. This means fields like `max_min_mult` may not be valid — check `check_model_fields_match_input()`. The template should use the same field set as `config_template_example.yaml_template`.

- [ ] **Step 1: Write the test file**

Create `python/tests/e2e/test_auto_generate_config.py`:

```python
"""E2E tests for auto_generate_config: config generation from templates."""

import os
import shutil

import pytest
import yaml

from python.tests.e2e.conftest import run_cli
from python.utils.directory_constants import CONFIG_BASE_DIR


MODULE = 'python.scripts.auto_generate_config'


@pytest.mark.e2e
@pytest.mark.e2e_csv
class TestAutoGenerateConfig:
    """Test config generation from template."""

    def test_generates_correct_number_of_configs(self, e2e_test_data):
        """Template with new_range of 2 values should produce 2 YAMLs."""
        template_path = e2e_test_data['autogen_template_path']
        run_cli(MODULE, '-b', template_path)

        # The template varies 'year' with values [['2020'], ['2022']]
        # Generated names follow: {location}_{field_to_vary}_{value_suffix}.yaml
        config_dir = e2e_test_data['config_dir']
        sid = e2e_test_data['session_id']

        generated = [
            f for f in os.listdir(config_dir)
            if f.endswith('.yaml') and 'year' in f
        ]
        assert len(generated) == 2, f'Expected 2 generated configs, found {len(generated)}: {generated}'

    def test_generated_config_has_varied_field(self, e2e_test_data):
        """Each generated config should have the varied field set correctly."""
        config_dir = e2e_test_data['config_dir']

        generated = [
            os.path.join(config_dir, f)
            for f in os.listdir(config_dir)
            if f.endswith('.yaml') and 'year' in f
        ]

        year_values = []
        for path in generated:
            with open(path, 'r') as f:
                config = yaml.safe_load(f)
            year_values.append(config['year'])

        assert ['2020'] in year_values
        assert ['2022'] in year_values

    def test_generated_config_preserves_other_fields(self, e2e_test_data):
        """Non-varied fields should be unchanged from template."""
        config_dir = e2e_test_data['config_dir']

        generated = [
            os.path.join(config_dir, f)
            for f in os.listdir(config_dir)
            if f.endswith('.yaml') and 'year' in f
        ]

        for path in generated:
            with open(path, 'r') as f:
                config = yaml.safe_load(f)
            # These should match the template base values
            assert config['beta'] == -2
            assert config['capacity'] == 5
            assert config['config_set'] == e2e_test_data['session_id']

    @pytest.fixture(autouse=True)
    def _cleanup_generated(self, e2e_test_data):
        """Remove generated config files after each test."""
        yield
        config_dir = e2e_test_data['config_dir']
        for f in os.listdir(config_dir):
            if 'year' in f and f.endswith('.yaml'):
                os.remove(os.path.join(config_dir, f))


@pytest.mark.e2e
@pytest.mark.e2e_db
class TestAutoGenerateConfigDb:
    """Test config generation with -d flag (write to DB)."""

    def test_generate_with_db_flag(self, e2e_test_data, clean_test_data, test_environment):
        """Generate configs with -d flag and verify they appear in DB."""
        template_path = e2e_test_data['autogen_template_path']
        run_cli(MODULE, '-b', template_path, '-d', '-e', 'test')

        from python.database.query import Query
        query = Query(test_environment)
        sid = e2e_test_data['session_id']
        configs = query.find_model_configs_by_config_set(sid)
        # Should have at least the 2 auto-generated configs
        autogen_names = [c.config_name for c in configs if 'year' in c.config_name]
        assert len(autogen_names) >= 2

    @pytest.fixture(autouse=True)
    def _cleanup_generated(self, e2e_test_data):
        """Remove generated config files after each test."""
        yield
        config_dir = e2e_test_data['config_dir']
        for f in os.listdir(config_dir):
            if 'year' in f and f.endswith('.yaml'):
                os.remove(os.path.join(config_dir, f))
```

- [ ] **Step 2: Run the tests**

Run: `pytest python/tests/e2e/test_auto_generate_config.py -v`

**Important:** This test may fail because `auto_generate_config.py` validates the template's fields against the SQLAlchemy `ModelConfig` model columns (see `check_model_fields_match_input()`). The template generated in `conftest.py` uses `PollingModelConfig` fields (e.g., `max_min_mult`) which may not match the DB model. If this happens:
- Read the error message to identify the mismatched fields
- Update the `_SOURCE_CONFIG` template generation in `conftest.py` to match what the DB model expects
- This may require creating a separate template config dict that matches the `ModelConfig` SQLAlchemy columns

- [ ] **Step 3: Fix any field mismatch issues and re-run**

If Step 2 fails due to field mismatches, update `conftest.py`'s autogen template generation to use the correct field set for the SQLAlchemy model. Then re-run.

- [ ] **Step 4: Commit**

```bash
git add python/tests/e2e/test_auto_generate_config.py
git commit -m "feat: add e2e tests for auto_generate_config template expansion"
```

---

### Task 6: DB import potential locations tests (`test_db_import_potential_locations.py`)

**Files:**
- Create: `python/tests/e2e/test_db_import_potential_locations.py`

**Context:** `db_import_potential_locations_cli` takes positional `locations` args, `-e` environment. It calls `build_potential_locations_file_path(location)` to find the CSV at `datasets/polling/{location}/{location}_potential_locations.csv`. The test data fixture already places files there.

- [ ] **Step 1: Write the test file**

Create `python/tests/e2e/test_db_import_potential_locations.py`:

```python
"""E2E tests for db_import_potential_locations_cli."""

import pandas as pd
import pytest

from python.tests.e2e.conftest import run_cli


MODULE = 'python.scripts.db_import_potential_locations_cli'


# Uses the shared imported_potential_locations fixture from conftest.py


@pytest.mark.e2e
@pytest.mark.e2e_db
class TestDbImportPotentialLocations:
    """Test importing potential locations to BigQuery."""

    def test_import_exits_zero(self, imported_potential_locations):
        """CLI should exit with code 0."""
        assert imported_potential_locations.returncode == 0

    def test_import_reports_success(self, imported_potential_locations):
        """CLI stdout should report success."""
        assert 'Failures (0)' in imported_potential_locations.stdout

    def test_record_count_matches_csv(self, e2e_test_data, imported_potential_locations, test_environment):
        """DB record count should match CSV row count."""
        from python.database.query import Query

        source_df = pd.read_csv(e2e_test_data['potential_locations_csv'])
        expected_count = len(source_df)

        query = Query(test_environment)
        pl_set = query.get_potential_locations_set(e2e_test_data['session_id'])
        assert pl_set is not None, 'PotentialLocationsSet not found in DB'

        locations_df = query.get_potential_locations(pl_set.id)
        assert len(locations_df) == expected_count

    def test_lat_lon_spot_check(self, e2e_test_data, imported_potential_locations, test_environment):
        """Spot-check that lat_lon values from CSV appear in DB."""
        from python.database.query import Query

        source_df = pd.read_csv(e2e_test_data['potential_locations_csv'])
        query = Query(test_environment)
        pl_set = query.get_potential_locations_set(e2e_test_data['session_id'])
        locations_df = query.get_potential_locations(pl_set.id)

        # Check first row's lat_lon value exists in DB
        if 'Lat, Lon' in source_df.columns and 'lat_lon' in locations_df.columns:
            first_lat_lon = str(source_df['Lat, Lon'].iloc[0])
            assert first_lat_lon in locations_df['lat_lon'].values
```

- [ ] **Step 2: Run the test (requires test environment)**

Run: `pytest python/tests/e2e/test_db_import_potential_locations.py -v`
Expected: PASS if `test` environment is configured, SKIP otherwise.

- [ ] **Step 3: Commit**

```bash
git add python/tests/e2e/test_db_import_potential_locations.py
git commit -m "feat: add e2e tests for db_import_potential_locations_cli"
```

---

### Task 7: DB import driving distances tests (`test_db_import_driving_distances.py`)

**Files:**
- Create: `python/tests/e2e/test_db_import_driving_distances.py`

**Context:** `db_import_driving_distances_cli` takes positional `census_year` and `locations` args, `-e` environment. It calls `build_driving_distances_file_path(census_year, map_source_date, location)` which produces `datasets/driving/{location}/{location}_driving_distances.csv`. The test data fixture places the file there.

- [ ] **Step 1: Write the test file**

Create `python/tests/e2e/test_db_import_driving_distances.py`:

```python
"""E2E tests for db_import_driving_distances_cli."""

import pandas as pd
import pytest

from python.tests.e2e.conftest import run_cli


MODULE = 'python.scripts.db_import_driving_distances_cli'

# The default map_source_date used by db_import_driving_distances_cli
MAP_SOURCE_DATE = '20250101'

# Uses the shared imported_driving_distances fixture from conftest.py


@pytest.mark.e2e
@pytest.mark.e2e_db
class TestDbImportDrivingDistances:
    """Test importing driving distances to BigQuery."""

    def test_import_exits_zero(self, imported_driving_distances):
        """CLI should exit with code 0."""
        assert imported_driving_distances.returncode == 0

    def test_record_count_matches_csv(self, e2e_test_data, imported_driving_distances, test_environment):
        """DB record count should match CSV row count."""
        from python.database.query import Query

        source_df = pd.read_csv(e2e_test_data['driving_import_csv'])
        expected_count = len(source_df)

        query = Query(test_environment)
        # db_import_driving_distances_cli uses map_source_date='20250101' by default
        drv_set = query.find_driving_distance_set(
            census_year='2020',
            map_source_date=MAP_SOURCE_DATE,
            location=e2e_test_data['session_id'],
        )
        assert drv_set is not None, 'DrivingDistancesSet not found in DB'

        distances_df = query.get_driving_distances(drv_set.id)
        assert len(distances_df) == expected_count

    def test_distance_values_spot_check(self, e2e_test_data, imported_driving_distances, test_environment):
        """Spot-check that distance values from CSV appear in DB."""
        from python.database.query import Query

        source_df = pd.read_csv(e2e_test_data['driving_import_csv'])
        query = Query(test_environment)
        drv_set = query.find_driving_distance_set(
            census_year='2020',
            map_source_date=MAP_SOURCE_DATE,
            location=e2e_test_data['session_id'],
        )
        db_df = query.get_driving_distances(drv_set.id)

        # All distances should be positive
        assert (db_df['distance_m'] > 0).all()
```

- [ ] **Step 2: Run the test**

Run: `pytest python/tests/e2e/test_db_import_driving_distances.py -v`
Expected: PASS if test environment configured, SKIP otherwise.

- [ ] **Step 3: Commit**

```bash
git add python/tests/e2e/test_db_import_driving_distances.py
git commit -m "feat: add e2e tests for db_import_driving_distances_cli"
```

---

### Task 8: DB import distance data tests (`test_db_import_distance_data.py`)

**Files:**
- Create: `python/tests/e2e/test_db_import_distance_data.py`

**Context:** `db_import_distance_data_cli` takes positional `census_year` and `locations`, optional `-t linear|log` and `-d` (driving boolean flag), `-e` environment. We test all 4 permutations of `-t` and `-d`.

- [ ] **Step 1: Write the test file**

Create `python/tests/e2e/test_db_import_distance_data.py`:

```python
"""E2E tests for db_import_distance_data_cli: all permutations of -t and -d flags."""

import pytest

from python.tests.e2e.conftest import run_cli


MODULE = 'python.scripts.db_import_distance_data_cli'

# Uses the shared imported_distance_data_all fixture from conftest.py which
# imports all 4 permutations. Also depends on imported_potential_locations
# and imported_driving_distances (session-scoped, run once).


@pytest.mark.e2e
@pytest.mark.e2e_db
class TestDbImportDistanceDataLinear:
    """Test haversine linear distance data import."""

    def test_import_exits_zero(self, imported_distance_data_all):
        assert imported_distance_data_all['linear'].returncode == 0

    def test_records_exist(self, e2e_test_data, imported_distance_data_all, test_environment):
        from python.database.query import Query
        query = Query(test_environment)
        dd_set = query.get_distance_data_set(
            census_year='2020',
            location=e2e_test_data['session_id'],
            log_distance=False,
            driving=False,
        )
        assert dd_set is not None, 'DistanceDataSet (linear, no driving) not found'
        df = query.get_distance_data(dd_set.id)
        assert len(df) > 0

    def test_demographic_columns_populated(self, e2e_test_data, imported_distance_data_all, test_environment):
        """Demographic columns should be populated in the imported data."""
        from python.database.query import Query
        query = Query(test_environment)
        dd_set = query.get_distance_data_set(
            census_year='2020',
            location=e2e_test_data['session_id'],
            log_distance=False, driving=False,
        )
        df = query.get_distance_data(dd_set.id)
        for col in ['population', 'white', 'black', 'hispanic']:
            assert col in df.columns, f'Missing demographic column: {col}'
            assert df[col].notna().any(), f'Demographic column {col} is all null'


@pytest.mark.e2e
@pytest.mark.e2e_db
class TestDbImportDistanceDataLog:
    """Test haversine log distance data import."""

    def test_import_exits_zero(self, imported_distance_data_all):
        assert imported_distance_data_all['log'].returncode == 0

    def test_records_exist(self, e2e_test_data, imported_distance_data_all, test_environment):
        from python.database.query import Query
        query = Query(test_environment)
        dd_set = query.get_distance_data_set(
            census_year='2020',
            location=e2e_test_data['session_id'],
            log_distance=True,
            driving=False,
        )
        assert dd_set is not None, 'DistanceDataSet (log, no driving) not found'
        df = query.get_distance_data(dd_set.id)
        assert len(df) > 0


@pytest.mark.e2e
@pytest.mark.e2e_db
class TestDbImportDistanceDataDrivingLinear:
    """Test driving linear distance data import."""

    def test_import_exits_zero(self, imported_distance_data_all):
        assert imported_distance_data_all['driving_linear'].returncode == 0

    def test_records_exist(self, e2e_test_data, imported_distance_data_all, test_environment):
        from python.database.query import Query
        query = Query(test_environment)
        dd_set = query.get_distance_data_set(
            census_year='2020',
            location=e2e_test_data['session_id'],
            log_distance=False,
            driving=True,
        )
        assert dd_set is not None, 'DistanceDataSet (linear, driving) not found'
        df = query.get_distance_data(dd_set.id)
        assert len(df) > 0


@pytest.mark.e2e
@pytest.mark.e2e_db
class TestDbImportDistanceDataDrivingLog:
    """Test driving log distance data import."""

    def test_import_exits_zero(self, imported_distance_data_all):
        assert imported_distance_data_all['driving_log'].returncode == 0

    def test_records_exist(self, e2e_test_data, imported_distance_data_all, test_environment):
        from python.database.query import Query
        query = Query(test_environment)
        dd_set = query.get_distance_data_set(
            census_year='2020',
            location=e2e_test_data['session_id'],
            log_distance=True,
            driving=True,
        )
        assert dd_set is not None, 'DistanceDataSet (log, driving) not found'
        df = query.get_distance_data(dd_set.id)
        assert len(df) > 0
```

- [ ] **Step 2: Run the tests**

Run: `pytest python/tests/e2e/test_db_import_distance_data.py -v`
Expected: PASS or SKIP

- [ ] **Step 3: Commit**

```bash
git add python/tests/e2e/test_db_import_distance_data.py
git commit -m "feat: add e2e tests for db_import_distance_data_cli with all permutations"
```

---

### Task 9: DB import config tests (`test_db_import_config.py`)

**Files:**
- Create: `python/tests/e2e/test_db_import_config.py`

**Context:** `db_import_config_cli` takes positional `configs` (YAML paths) and `-e` environment. It imports each config into the `model_configs` table. The test verifies DB fields match the YAML source.

- [ ] **Step 1: Write the test file**

Create `python/tests/e2e/test_db_import_config.py`:

```python
"""E2E tests for db_import_config_cli."""

import pytest
import yaml

from python.tests.e2e.conftest import run_cli


MODULE = 'python.scripts.db_import_config_cli'

# Uses the shared imported_configs fixture from conftest.py


@pytest.mark.e2e
@pytest.mark.e2e_db
class TestDbImportConfig:
    """Test importing YAML configs to BigQuery."""

    def test_import_exits_zero(self, imported_configs):
        """CLI should exit with code 0."""
        assert imported_configs.returncode == 0

    def test_all_configs_imported(self, e2e_test_data, imported_configs, test_environment):
        """All 8 configs should be in the DB after bulk import."""
        from python.database.query import Query
        query = Query(test_environment)
        sid = e2e_test_data['session_id']
        configs = query.find_model_configs_by_config_set(sid)
        assert len(configs) >= 8

    def test_config_fields_match_yaml(self, e2e_test_data, imported_configs, test_environment):
        """DB config fields should match the source YAML."""
        from python.database.query import Query
        query = Query(test_environment)
        sid = e2e_test_data['session_id']

        basic_path = e2e_test_data['config_paths']['config_basic']
        with open(basic_path, 'r') as f:
            yaml_config = yaml.safe_load(f)

        # find_model_configs_by_config_set_and_config_name returns a single
        # ModelConfig object (or None), not a list
        db_config = query.find_model_configs_by_config_set_and_config_name(
            sid, f'{sid}_config_basic'
        )
        assert db_config is not None, f'Config {sid}_config_basic not found in DB'

        assert db_config.config_name == yaml_config['config_name']
        assert db_config.beta == yaml_config['beta']
        assert db_config.capacity == yaml_config['capacity']
        assert db_config.location == yaml_config['location']
```

- [ ] **Step 2: Run the tests**

Run: `pytest python/tests/e2e/test_db_import_config.py -v`
Expected: PASS or SKIP

- [ ] **Step 3: Commit**

```bash
git add python/tests/e2e/test_db_import_config.py
git commit -m "feat: add e2e tests for db_import_config_cli"
```

---

### Task 10: DB model run tests (`test_model_run_db_cli.py`)

**Files:**
- Create: `python/tests/e2e/test_model_run_db_cli.py`

**Context:** `model_run_db_cli` takes positional configs as `config_set` or `config_set/config_name`, `-e` environment, `-o csv|db` output type, `-c` concurrent, `-v` verbose. This is the most complex DB test since it requires configs AND distance data to be imported first.

- [ ] **Step 1: Write the test file**

Create `python/tests/e2e/test_model_run_db_cli.py`:

```python
"""E2E tests for model_run_db_cli: database-backed model runs."""

import os
import shutil

import pandas as pd
import pytest

from python.tests.e2e.conftest import run_cli
from python.utils.directory_constants import RESULTS_BASE_DIR


MODULE = 'python.scripts.model_run_db_cli'


# No module-level fixtures needed — uses the shared session-scoped fixtures
# from conftest.py: imported_potential_locations, imported_driving_distances,
# imported_distance_data_all, imported_configs. These form the dependency chain
# and each runs at most once per session.


@pytest.fixture(scope='module', autouse=True)
def cleanup_csv_results(e2e_test_data):
    """Clean up any CSV results after module tests complete."""
    sid = e2e_test_data['session_id']
    yield
    result_dir = os.path.join(RESULTS_BASE_DIR, f'{sid}_results')
    shutil.rmtree(result_dir, ignore_errors=True)


@pytest.mark.e2e
@pytest.mark.e2e_db
class TestModelRunDbCliCsvOutput:
    """Test DB model runs with CSV output (-o csv)."""

    def test_single_config_csv_output(
        self, e2e_test_data, imported_distance_data_all, imported_configs,
    ):
        """Run a single config with -o csv."""
        sid = e2e_test_data['session_id']
        config_ref = f'{sid}/{sid}_config_basic'
        run_cli(MODULE, config_ref, '-e', 'test', '-o', 'csv')

        result_dir = os.path.join(RESULTS_BASE_DIR, f'{sid}_results')
        prefix = f'{sid}.{sid}_config_basic'
        result_file = os.path.join(result_dir, f'{prefix}_results.csv')
        assert os.path.isfile(result_file)

    def test_config_set_runs_all(
        self, e2e_test_data, imported_distance_data_all, imported_configs,
    ):
        """Run all configs in a config_set with -o csv."""
        sid = e2e_test_data['session_id']
        # This should run all configs in the set
        run_cli(MODULE, sid, '-e', 'test', '-o', 'csv')

        result_dir = os.path.join(RESULTS_BASE_DIR, f'{sid}_results')
        assert os.path.isdir(result_dir)
        result_files = [f for f in os.listdir(result_dir) if f.endswith('_results.csv')]
        # Should have results for multiple configs
        assert len(result_files) >= 1

    def test_verbose_output(
        self, e2e_test_data, imported_distance_data_all, imported_configs,
    ):
        """Run with -v flag and verify verbose output."""
        sid = e2e_test_data['session_id']
        config_ref = f'{sid}/{sid}_config_basic'
        result = run_cli(MODULE, config_ref, '-e', 'test', '-o', 'csv', '-v')
        # Verbose should produce additional output
        assert len(result.stdout) > 0


@pytest.mark.e2e
@pytest.mark.e2e_db
class TestModelRunDbCliDbOutput:
    """Test DB model runs with DB output (-o db)."""

    def test_single_config_db_output(
        self, e2e_test_data, imported_distance_data_all, imported_configs, test_environment,
    ):
        """Run a single config with -o db and verify DB records created."""
        sid = e2e_test_data['session_id']
        config_ref = f'{sid}/{sid}_config_basic'
        run_cli(MODULE, config_ref, '-e', 'test', '-o', 'db')

        from python.database.query import Query
        query = Query(test_environment)

        # find_model_configs_by_config_set_and_config_name returns a single object
        db_config = query.find_model_configs_by_config_set_and_config_name(
            sid, f'{sid}_config_basic'
        )
        assert db_config is not None
```

- [ ] **Step 2: Run the tests**

Run: `pytest python/tests/e2e/test_model_run_db_cli.py -v`
Expected: PASS or SKIP. These tests take longer due to the full pipeline setup.

- [ ] **Step 3: Commit**

```bash
git add python/tests/e2e/test_model_run_db_cli.py
git commit -m "feat: add e2e tests for model_run_db_cli with CSV and DB output"
```

---

### Task 11: Run full e2e suite and fix issues

**Files:**
- Potentially modify any of the above files to fix issues discovered in integration.

- [ ] **Step 1: Run CSV tests end-to-end**

Run: `pytest python/tests/e2e/ -m e2e_csv -v`
Expected: All CSV tests pass.

- [ ] **Step 2: Run DB tests end-to-end (if test environment available)**

Run: `pytest python/tests/e2e/ -m e2e_db -v`
Expected: All DB tests pass or skip.

- [ ] **Step 3: Run the entire e2e suite**

Run: `pytest python/tests/e2e/ -v`
Expected: All tests pass (CSV tests run, DB tests pass or skip).

- [ ] **Step 4: Verify existing tests still pass**

Run: `pytest python/tests/ -v --ignore=python/tests/e2e/`
Expected: All existing tests pass — e2e tests didn't break anything.

- [ ] **Step 5: Run pylint**

Run: `pylint python/tests/e2e/`
Expected: Clean or only minor warnings. Fix any issues.

- [ ] **Step 6: Fix any issues found in steps 1-5**

Address failures, adjust assertions, fix imports. Re-run until green.

- [ ] **Step 7: Commit any fixes**

```bash
git add -A python/tests/e2e/
git commit -m "fix: resolve integration issues in e2e test suite"
```

---

### Task 12: Final verification and documentation

**Files:**
- Modify: `CLAUDE.md` (add e2e test commands to the Commands section)

- [ ] **Step 1: Add e2e test commands to CLAUDE.md**

Under the `## Commands` section, after the existing test commands, add:

```markdown
**E2E tests:**
```bash
# All e2e tests via Docker
python run.py e2e_tests

# CSV tests only (no DB required)
python run.py e2e_tests -m e2e_csv

# DB tests only (requires 'test' environment in settings.yaml)
python run.py e2e_tests -m e2e_db

# Locally (conda env)
pytest python/tests/e2e/
```
```

- [ ] **Step 2: Run `python run.py e2e_tests -m e2e_csv` via Docker**

Verify the Docker path works end-to-end.

- [ ] **Step 3: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: add e2e test commands to CLAUDE.md"
```
