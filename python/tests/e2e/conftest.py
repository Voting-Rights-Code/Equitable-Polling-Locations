"""Core e2e test infrastructure: fixtures, CLI helper, and shared test data setup."""

# pylint: disable=redefined-outer-name

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
    CONFIG_BASE_DIR,
    DRIVING_DIR,
    POLLING_DIR,
    SETTINGS_PATH,
)

# ---------------------------------------------------------------------------
# Source data paths (committed testing fixtures)
# ---------------------------------------------------------------------------

_TESTING_POLLING_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', '..', '..', 'datasets', 'polling', 'testing',
)
_TESTING_CONFIG_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', '..', '..', 'datasets', 'configs', 'testing',
)

_SRC_POTENTIAL_LOCATIONS = os.path.join(_TESTING_POLLING_DIR, 'testing_potential_locations.csv')
_SRC_DISTANCES = os.path.join(_TESTING_POLLING_DIR, 'testing_distances_2020.csv')
_SRC_DRIVING_DISTANCES = os.path.join(_TESTING_POLLING_DIR, 'testing_driving_2020.csv')
_SRC_BASE_CONFIG = os.path.join(_TESTING_CONFIG_DIR, 'testing_config_no_bg.yaml')

# ---------------------------------------------------------------------------
# Config variants
# ---------------------------------------------------------------------------
#
# Curated cross-section of solver-config "knobs" the e2e suite exercises.
# NOT a complete enumeration of every PollingModelConfig field (the full
# config has ~30 fields; this dict toggles 7 of them).
#
# Each entry maps a variant suffix to override fields applied on top of a
# single base config template by `_make_config()` (below).  NOT a 1-to-1
# map to the files in `datasets/configs/testing/` — those pair with the
# committed result baselines in `datasets/results/testing_results/`,
# which the e2e column-set asserts also reference.
#
# What each variant is used for in the test suite:
#
#   - config_basic         baseline; the reference for "different config ->
#                          different output" assertions and the smoke-test
#                          default.
#   - config_driving       exercises the driving-distance input path.
#   - config_log           exercises the log-distance input transform.
#   - config_driving_log   the one combinatorial variant — verifies driving
#                          and log-distance flags compose without breaking.
#   - config_penalty       exercises the penalized_sites mechanism via
#                          test_penalty_config (smoke run).
#   - config_low_beta      paired with config_basic to assert beta actually
#                          affects EDE values (difference-detector).
#   - config_low_capacity  paired with config_fixed_capacity to isolate the
#                          effect of fixed_capacity_site_number; same
#                          capacity=2.5 and precincts_open=4, no fixed cap.
#   - config_fixed_capacity exercises the fixed_capacity_site_number
#                          substitution in model_factory.py:257-261 — same
#                          base as config_low_capacity but with
#                          fixed_capacity_site_number=3.
#   - config_bad_types     exercises bad_types end-to-end; uses the same
#                          value as testing_config_no_bg_school.yaml
#                          (['bg_centroid', 'Elec Day School - Potential'])
#                          which is paired with committed result baselines
#                          and proven feasible.
#   - config_year          exercises the year filter end-to-end. The test
#                          fixture only encodes years in the EV_2022_2020
#                          polling type so the e2e assertion is vacuously
#                          true today; the assertion shape generalizes if
#                          the fixture later gains year-distinct types.
#
# Fields deliberately NOT varied here include time_limit, limits_gap,
# max_min_mult, etc.  e2e tests cover
# CLI plumbing and result-shape invariants — not solver parameter-space
# coverage, which belongs in unit tests against the solver directly.

CONFIG_VARIANTS = {
    'config_basic': {},
    'config_driving': {'driving': True, 'metric': 'driving_distance'},
    'config_driving_duration': {'driving': True, 'metric': 'driving_time'},
    'config_log': {'log_distance': True},
    'config_driving_log': {'driving': True, 'log_distance': True, 'metric': 'driving_distance'},
    'config_penalty': {'penalized_sites': ['College Campus - Potential', 'Fire Station - Potential']},
    'config_low_beta': {'beta': -1},
    'config_low_capacity': {'capacity': 2.5, 'precincts_open': 4},
    'config_fixed_capacity': {'capacity': 2.5, 'precincts_open': 4, 'fixed_capacity_site_number': 3},
    'config_bad_types': {'bad_types': ['bg_centroid', 'Elec Day School - Potential']},
    'config_year': {'year': ['2020']},
}

# ---------------------------------------------------------------------------
# Module-level CLI helper (not a fixture)
# ---------------------------------------------------------------------------


def run_cli(script_module: str, *args, timeout: int = 600) -> subprocess.CompletedProcess:
    """Run a Python script module as a subprocess and assert it exits cleanly.

    Args:
        script_module: Dotted module path passed to ``python -m`` (e.g.
            ``'python.scripts.db_import_config_cli'``).
        *args: Additional positional arguments forwarded to the script.
        timeout: Maximum number of seconds to wait before killing the process.

    Returns:
        The completed :class:`subprocess.CompletedProcess` instance.

    Raises:
        AssertionError: If the subprocess exits with a non-zero return code.
    """
    cmd = [sys.executable, '-m', script_module] + [str(a) for a in args]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    assert result.returncode == 0, (
        f"Command {cmd} exited with code {result.returncode}.\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )
    return result


# ---------------------------------------------------------------------------
# Pytest hooks
# ---------------------------------------------------------------------------


def _db_config_status() -> tuple[bool, str]:
    """Check whether settings.yaml is configured for DB e2e tests.

    Returns:
        A tuple ``(ok, reason)``. ``ok`` is True when settings.yaml exists
        and has a ``test`` entry; False otherwise. ``reason`` is a short
        human-readable explanation suitable for inclusion in error or
        warning messages.
    """
    if not os.path.isfile(SETTINGS_PATH):
        return False, f'settings.yaml is missing at {SETTINGS_PATH}'
    with open(SETTINGS_PATH, 'r', encoding='utf-8') as fh:
        all_configs: dict = yaml.safe_load(fh) or {}
    if 'test' not in all_configs:
        return False, 'settings.yaml has no \'test\' environment entry'
    return True, 'settings.yaml has a \'test\' entry'


@pytest.hookimpl(trylast=True)
def pytest_collection_modifyitems(config, items):
    """Surface missing DB configuration when DB e2e tests are collected.

    Two branches:

    * **Strict exit:** if every collected test is marked ``e2e_db`` (e.g.
      ``pytest -m e2e_db`` or pointing pytest at a DB-only test file), the
      user has explicitly opted into DB testing. A missing ``settings.yaml``
      or missing ``test`` entry aborts the session via :func:`pytest.exit`
      so the failure is impossible to miss.
    * **Visibility banner:** in mixed runs (CSV + DB together, or no marker)
      the per-test :func:`test_environment` fixture still handles skips
      gracefully — but pytest only shows ``S`` per skipped test in default
      output, which can read as silent. If any ``e2e_db`` items are
      collected and DB config is incomplete, emit a single prominent
      banner at collection time so the user sees why those tests will skip
      without needing ``-rs``.
    """
    if not items:
        return

    db_items = [item for item in items if item.get_closest_marker('e2e_db')]
    if not db_items:
        return  # No DB tests collected — nothing to warn about.

    ok, reason = _db_config_status()
    if ok:
        return  # DB config is fine — no warning needed.

    if len(db_items) == len(items):
        pytest.exit(
            f'DB tests were explicitly selected, but {reason}. '
            f'Configure a \'test\' environment before running -m e2e_db. '
            f'See CONTRIBUTING.md: Setting Up DB Tests.',
            returncode=1,
        )

    # Mixed run: emit a prominent banner. Tests still skip individually.
    bar = '=' * 80
    msg_lines = [
        bar,
        f'DB e2e tests will be skipped: {len(db_items)} tests marked e2e_db, '
        f'but {reason}.',
        'To enable: configure a \'test\' environment in settings.yaml. See',
        'CONTRIBUTING.md → "Setting Up DB Tests".',
        bar,
    ]
    reporter = config.pluginmanager.get_plugin('terminalreporter')
    if reporter is not None:
        for line in msg_lines:
            reporter.write_line(line, bold=True, yellow=True)
    else:
        for line in msg_lines:
            print(line, file=sys.stderr)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _apply_log_transform(src_path: str, dest_path: str) -> None:
    """Read a distance CSV and write a copy with log-transformed distance_m values.

    Args:
        src_path: Path to the source CSV file containing a ``distance_m`` column.
        dest_path: Path where the log-transformed CSV will be written.

    Raises:
        ValueError: If any ``distance_m`` value is non-positive. ``log`` is
            undefined there, and a non-positive distance indicates upstream
            data corruption — surface it rather than silently mask.
    """
    df = pd.read_csv(src_path)
    bad_count = int((df['distance_m'] <= 0).sum())
    if bad_count > 0:
        raise ValueError(
            f"{bad_count} rows in {src_path} have distance_m <= 0; "
            f"log transform is undefined."
        )
    df['distance_m'] = df['distance_m'].apply(math.log)
    df.to_csv(dest_path, index=False)


def _make_config(base: dict, sid: str, suffix: str, overrides: dict) -> dict:
    """Return a config dict derived from *base* with e2e-specific fields applied.

    Used by the ``e2e_test_data`` session fixture to synthesize each
    :data:`CONFIG_VARIANTS` entry from a single in-memory base template (the
    e2e variants are NOT loaded from on-disk files in
    ``datasets/configs/testing/``).  See the CONFIG_VARIANTS comment block at
    the top of this file for the full trace.

    Args:
        base: The base configuration loaded from the template YAML.
        sid: The session ID used as both ``config_set`` and ``location``.
        suffix: The config variant name, appended to *sid* to form ``config_name``.
        overrides: Field overrides specific to this config variant.

    Returns:
        A new dict suitable for writing as a YAML config file.
    """
    cfg = dict(base)
    cfg['config_set'] = sid
    cfg['config_name'] = f'{sid}_{suffix}'
    cfg['location'] = sid
    cfg.update(overrides)
    return cfg


# ---------------------------------------------------------------------------
# Session-scoped fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope='session')
def e2e_session_id() -> str:
    """Return a unique session identifier prefixed with ``e2e_``.

    Returns:
        A string of the form ``e2e_<6 hex chars>``.
    """
    return f'e2e_{uuid.uuid4().hex[:6]}'


@pytest.fixture(scope='session')
def e2e_test_data(e2e_session_id, pytestconfig):
    """Create isolated test data directories and files for the e2e session.

    Copies source testing CSVs into location-namespaced subdirectories, creates
    log-transformed distance variants, and generates config YAML files from the
    base template with each variant in :data:`CONFIG_VARIANTS`.

    Also creates an autogen template (``.yaml_template``) that varies over
    ``year`` with both 2020 and 2022, and an explicit driving/log/penalized_sites
    block.

    Args:
        e2e_session_id: The session identifier fixture.
        pytestconfig: The pytest config object, used to read
            ``--keep-e2e-outputs``.

    Yields:
        dict: A mapping of path keys to absolute paths:

            - ``sid``: the session ID string
            - ``polling_dir``: ``{POLLING_DIR}/{sid}``
            - ``driving_dir``: ``{DRIVING_DIR}/{sid}``
            - ``config_dir``: ``{CONFIG_BASE_DIR}/{sid}``
            - ``potential_locations``: path to the copied potential locations CSV
            - ``distances``: path to the linear distances CSV
            - ``distances_log``: path to the log-transformed distances CSV
            - ``driving_distances``: path to the driving distances CSV (polling dir)
            - ``driving_distances_log``: path to the log-transformed driving CSV
            - ``driving_distances_import``: path to driving distances CSV (driving dir)
            - ``configs``: dict mapping each variant suffix to its YAML file path
            - ``autogen_template``: path to the ``.yaml_template`` file

    Cleanup:
        Removes the three created directories and all their contents after the
        session completes, regardless of test outcome. Skipped when
        ``--keep-e2e-outputs`` is passed; in that case the retained paths are
        printed to stderr.
    """
    sid = e2e_session_id

    polling_subdir = os.path.join(POLLING_DIR, sid)
    driving_subdir = os.path.join(DRIVING_DIR, sid)
    config_subdir = os.path.join(CONFIG_BASE_DIR, sid)

    os.makedirs(polling_subdir, exist_ok=True)
    os.makedirs(driving_subdir, exist_ok=True)
    os.makedirs(config_subdir, exist_ok=True)

    # --- CSV files -----------------------------------------------------------

    potential_locations_path = os.path.join(polling_subdir, f'{sid}_potential_locations.csv')
    distances_path = os.path.join(polling_subdir, f'{sid}_distances_2020.csv')
    distances_log_path = os.path.join(polling_subdir, f'{sid}_distances_2020_log.csv')
    driving_distances_path = os.path.join(polling_subdir, f'{sid}_driving_distances_2020.csv')
    driving_distances_log_path = os.path.join(polling_subdir, f'{sid}_driving_distances_2020_log.csv')
    driving_distances_import_path = os.path.join(driving_subdir, f'{sid}_driving_distances.csv')

    shutil.copy(_SRC_POTENTIAL_LOCATIONS, potential_locations_path)
    shutil.copy(_SRC_DISTANCES, distances_path)
    # Stage driving distances with a synthesized duration_s column so the
    # driving_time metric path has data. duration_s is derived from distance_m
    # (synthetic; magnitude is irrelevant to the pipeline under test).
    staged_driving_df = pd.read_csv(_SRC_DRIVING_DISTANCES)
    if 'duration_s' not in staged_driving_df.columns:
        staged_driving_df['duration_s'] = staged_driving_df['distance_m'] / 10.0
    staged_driving_df.to_csv(driving_distances_path, index=False)
    # The db_import_driving_distances_cli expects columns matching the
    # DrivingDistance model (id_orig, id_dest, distance_m, duration_s) plus V1
    # (ignored). The source CSV has extra columns (county, demographics, etc.)
    # that would cause a BigQuery schema mismatch, so strip to the model columns.
    # duration_s is synthesized (the source has none) so the driving_time
    # metric round-trips through the DB.
    _driving_df = pd.read_csv(_SRC_DRIVING_DISTANCES)
    if 'duration_s' not in _driving_df.columns:
        _driving_df['duration_s'] = _driving_df['distance_m'] / 10.0
    _driving_df[['id_orig', 'id_dest', 'distance_m', 'duration_s']].to_csv(
        driving_distances_import_path, index=False,
    )

    _apply_log_transform(_SRC_DISTANCES, distances_log_path)
    # Log-transform the synthesized driving CSV (not the raw source) so the
    # log-driving distance data keeps the duration_s column. _apply_log_transform
    # only logs distance_m; duration_s stays as the raw synthetic value (positive).
    _apply_log_transform(driving_distances_path, driving_distances_log_path)

    # --- DB-import-ready distance CSVs (stripped of 'county' column) ----------
    # The db_import_distance_data_cli import function ignores 'id' and 'V1'
    # but 'county' is not in the DistanceData model and would cause a schema
    # mismatch.  Create import-ready copies with 'county' removed.
    distance_data_import_cols = [
        'id_orig', 'id_dest', 'distance_m', 'duration_s', 'address', 'dest_lat',
        'dest_lon', 'orig_lat', 'orig_lon', 'location_type', 'dest_type',
        'population', 'hispanic', 'non_hispanic', 'white', 'black', 'native',
        'asian', 'pacific_islander', 'other', 'multiple_races', 'source',
    ]

    distances_import_path = os.path.join(polling_subdir, f'{sid}_distances_2020_import.csv')
    distances_log_import_path = os.path.join(polling_subdir, f'{sid}_distances_2020_log_import.csv')
    driving_distances_import_dd_path = os.path.join(
        polling_subdir, f'{sid}_driving_distances_2020_import.csv',
    )
    driving_distances_log_import_dd_path = os.path.join(
        polling_subdir, f'{sid}_driving_distances_2020_log_import.csv',
    )

    for src, dest in [
        (distances_path, distances_import_path),
        (distances_log_path, distances_log_import_path),
        (driving_distances_path, driving_distances_import_dd_path),
        (driving_distances_log_path, driving_distances_log_import_dd_path),
    ]:
        df = pd.read_csv(src)
        df[[c for c in distance_data_import_cols if c in df.columns]].to_csv(dest, index=False)

    # --- Config YAMLs --------------------------------------------------------

    with open(_SRC_BASE_CONFIG, 'r', encoding='utf-8') as fh:
        base_config = yaml.safe_load(fh)

    config_paths = {}
    for suffix, overrides in CONFIG_VARIANTS.items():
        cfg = _make_config(base_config, sid, suffix, overrides)
        config_path = os.path.join(config_subdir, f'{sid}_{suffix}.yaml')
        with open(config_path, 'w', encoding='utf-8') as fh:
            yaml.dump(cfg, fh, default_flow_style=False, allow_unicode=True)
        config_paths[suffix] = config_path

    # --- Autogen template ----------------------------------------------------

    autogen_template = dict(base_config)
    autogen_template['config_set'] = sid
    autogen_template['config_name'] = f'{sid}_autogen'
    autogen_template['location'] = sid
    autogen_template['census_year'] = '2020'
    autogen_template['field_to_vary'] = 'year'
    autogen_template['new_range'] = [['2020'], ['2022']]
    autogen_template['driving'] = False
    autogen_template['log_distance'] = False
    # The autogen template runs with driving=False, so metric must be haversine
    # to satisfy the metric/driving agreement check.
    autogen_template['metric'] = 'haversine'
    autogen_template['penalized_sites'] = []

    autogen_template_path = os.path.join(config_subdir, f'{sid}_autogen.yaml_template')
    with open(autogen_template_path, 'w', encoding='utf-8') as fh:
        yaml.dump(autogen_template, fh, default_flow_style=False, allow_unicode=True)

    yield {
        'sid': sid,
        'polling_dir': polling_subdir,
        'driving_dir': driving_subdir,
        'config_dir': config_subdir,
        'potential_locations': potential_locations_path,
        'distances': distances_path,
        'distances_log': distances_log_path,
        'driving_distances': driving_distances_path,
        'driving_distances_log': driving_distances_log_path,
        'driving_distances_import': driving_distances_import_path,
        'distances_import': distances_import_path,
        'distances_log_import': distances_log_import_path,
        'driving_distances_import_dd': driving_distances_import_dd_path,
        'driving_distances_log_import_dd': driving_distances_log_import_dd_path,
        'configs': config_paths,
        'autogen_template': autogen_template_path,
    }

    # Teardown — remove the directories unless --keep-e2e-outputs was passed.
    keep_outputs = pytestconfig.getoption('--keep-e2e-outputs')
    for dirpath in (polling_subdir, driving_subdir, config_subdir):
        if not os.path.isdir(dirpath):
            continue
        if keep_outputs:
            print(f'[--keep-e2e-outputs] retained: {dirpath}', file=sys.stderr)
        else:
            shutil.rmtree(dirpath)


@pytest.fixture(scope='session')
def test_environment():
    """Load the 'test' environment from settings.yaml.

    Skips when DB testing has not been configured (no settings.yaml or no 'test'
    entry). When a 'test' environment IS configured, the user has opted into
    DB testing — a connection failure (expired GCP credentials, unreachable
    BigQuery, etc.) surfaces as an error rather than a skip so that broken
    setups cannot silently pass.

    Yields:
        :class:`python.utils.environments.Environment`: The loaded test environment.

    Raises:
        pytest.skip: If ``settings.yaml`` does not exist or has no 'test' entry.
    """
    # Imports here to avoid circular imports at collection time.
    from python.utils.environments import load_env  # pylint: disable=import-outside-toplevel
    from python.database import sqlalchemy_main  # pylint: disable=import-outside-toplevel

    if not os.path.isfile(SETTINGS_PATH):
        pytest.skip(f'settings.yaml not found at {SETTINGS_PATH}; DB tests skipped.')

    with open(SETTINGS_PATH, 'r', encoding='utf-8') as fh:
        all_configs: dict = yaml.safe_load(fh) or {}

    if 'test' not in all_configs:
        pytest.skip("No 'test' environment in settings.yaml; DB tests skipped.")

    env = load_env('test')

    # settings.yaml has a 'test' entry, so the user has opted into DB testing.
    # create_engine() is lazy — probe real connectivity here so failures surface
    # up front instead of mid-test with confusing downstream errors.
    engine = sqlalchemy_main.setup(env)
    engine.connect().close()

    yield env


# ---------------------------------------------------------------------------
# Shared DB import fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope='session')
def imported_potential_locations(e2e_test_data, test_environment):
    """Import potential locations for the e2e session into the DB.

    Args:
        e2e_test_data: Session-scoped test data dict from :func:`e2e_test_data`.
        test_environment: The loaded test environment.

    Returns:
        None
    """
    sid = e2e_test_data['sid']
    run_cli('python.scripts.db_import_potential_locations_cli', sid, '-e', 'test')


@pytest.fixture(scope='session')
def imported_driving_distances(e2e_test_data, test_environment):
    """Import driving distances for the e2e session into the DB.

    Args:
        e2e_test_data: Session-scoped test data dict from :func:`e2e_test_data`.
        test_environment: The loaded test environment.

    Returns:
        None
    """
    sid = e2e_test_data['sid']
    run_cli('python.scripts.db_import_driving_distances_cli', '2020', sid, '-e', 'test')


@pytest.fixture(scope='session')
def imported_distance_data_all(
    e2e_test_data,
    test_environment,
    imported_potential_locations,
    imported_driving_distances,
):
    """Import all four distance-data permutations for the e2e session into the DB.

    Rather than calling ``db_import_distance_data_cli`` (which rebuilds distance
    data from Census Tiger shapefiles — a cross-join producing ~500 MB for a
    full county), this fixture directly imports the pre-computed test CSV data.
    It creates the ``DistanceDataSet`` records and uses the CLI's
    ``import_distance_data`` function to load the CSV rows.

    The four permutations are:

    - linear haversine (no flags)
    - log haversine (``-t log``)
    - linear driving (``-d``)
    - log driving (``-t log -d``)

    Args:
        e2e_test_data: Session-scoped test data dict from :func:`e2e_test_data`.
        test_environment: The loaded test environment.
        imported_potential_locations: Ensures potential locations are already in DB.
        imported_driving_distances: Ensures driving distances are already in DB.

    Returns:
        None
    """
    # Import lazily to avoid pulling in DB/CLI dependencies at collection time.
    from python.database.query import Query  # pylint: disable=import-outside-toplevel
    from python.scripts.db_import_distance_data_cli import import_distance_data  # pylint: disable=import-outside-toplevel

    sid = e2e_test_data['sid']
    census_year = '2020'

    query = Query(test_environment)

    # Look up the set IDs created by earlier import fixtures.
    # Capture scalar IDs immediately — commit() will expire ORM objects.
    pl_set = query.get_potential_locations_set(sid)
    assert pl_set is not None, f"PotentialLocationsSet not found for '{sid}'"
    pl_set_id = pl_set.id

    driving_set = query.find_driving_distance_set(census_year, '20250101', sid)
    driving_set_id = driving_set.id if driving_set else None

    permutations = [
        # (log_distance, driving, csv_key)
        (False, False, 'distances_import'),
        (True, False, 'distances_log_import'),
        (False, True, 'driving_distances_import_dd'),
        (True, True, 'driving_distances_log_import_dd'),
    ]

    for log_distance, driving, csv_key in permutations:
        ds = query.create_db_distance_data_set(
            potential_locations_set_id=pl_set_id,
            census_year=census_year,
            location=sid,
            log_distance=log_distance,
            driving=driving,
            driving_distance_set_id=driving_set_id if driving else None,
        )
        # Capture the id before commit() expires the ORM object.
        ds_id = ds.id
        query.commit()

        csv_path = e2e_test_data[csv_key]
        result = import_distance_data(
            environment=test_environment,
            location=sid,
            distance_data_set_id=ds_id,
            csv_path=csv_path,
        )
        assert result.success, (
            f"Distance data import failed for log_distance={log_distance}, "
            f"driving={driving}: {result.exception}"
        )


@pytest.fixture(scope='session')
def imported_configs(e2e_test_data, test_environment):
    """Import all variant config YAML files for the e2e session into the DB.

    Args:
        e2e_test_data: Session-scoped test data dict from :func:`e2e_test_data`.
        test_environment: The loaded test environment.

    Returns:
        None
    """
    config_paths = list(e2e_test_data['configs'].values())
    run_cli('python.scripts.db_import_config_cli', *config_paths, '-e', 'test')
