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
# Helpers
# ---------------------------------------------------------------------------


def _apply_log_transform(src_path: str, dest_path: str) -> None:
    """Read a distance CSV and write a copy with log-transformed distance_m values.

    Values that are zero or negative are left unchanged (log is undefined there).

    Args:
        src_path: Path to the source CSV file containing a ``distance_m`` column.
        dest_path: Path where the log-transformed CSV will be written.
    """
    df = pd.read_csv(src_path)
    df['distance_m'] = df['distance_m'].apply(lambda x: math.log(x) if x > 0 else x)
    df.to_csv(dest_path, index=False)


def _make_config(base: dict, sid: str, suffix: str, overrides: dict) -> dict:
    """Return a config dict derived from *base* with e2e-specific fields applied.

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
def e2e_test_data(e2e_session_id):
    """Create isolated test data directories and files for the e2e session.

    Copies source testing CSVs into location-namespaced subdirectories, creates
    log-transformed distance variants, and generates config YAML files from the
    base template with each variant in :data:`CONFIG_VARIANTS`.

    Also creates an autogen template (``.yaml_template``) that varies over
    ``year`` with both 2020 and 2022, and an explicit driving/log/penalized_sites
    block.

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
        session completes, regardless of test outcome.
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
    shutil.copy(_SRC_DRIVING_DISTANCES, driving_distances_path)
    # The db_import_driving_distances_cli only expects columns matching the
    # DrivingDistance model (id_orig, id_dest, distance_m) plus V1 (ignored).
    # The source CSV has extra columns (county, demographics, etc.) that would
    # cause a BigQuery schema mismatch, so strip to the required columns.
    _driving_df = pd.read_csv(_SRC_DRIVING_DISTANCES)
    _driving_df[['id_orig', 'id_dest', 'distance_m']].to_csv(
        driving_distances_import_path, index=False,
    )

    _apply_log_transform(_SRC_DISTANCES, distances_log_path)
    _apply_log_transform(_SRC_DRIVING_DISTANCES, driving_distances_log_path)

    # --- DB-import-ready distance CSVs (stripped of 'county' column) ----------
    # The db_import_distance_data_cli import function ignores 'id' and 'V1'
    # but 'county' is not in the DistanceData model and would cause a schema
    # mismatch.  Create import-ready copies with 'county' removed.
    distance_data_import_cols = [
        'id_orig', 'id_dest', 'distance_m', 'address', 'dest_lat', 'dest_lon',
        'orig_lat', 'orig_lon', 'location_type', 'dest_type', 'population',
        'hispanic', 'non_hispanic', 'white', 'black', 'native', 'asian',
        'pacific_islander', 'other', 'multiple_races', 'source',
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

    # Teardown — remove the directories unconditionally.
    for dirpath in (polling_subdir, driving_subdir, config_subdir):
        if os.path.isdir(dirpath):
            shutil.rmtree(dirpath)


@pytest.fixture(scope='session')
def test_environment():
    """Load the 'test' environment from settings.yaml, skipping if not configured.

    Yields:
        :class:`python.utils.environments.Environment`: The loaded test environment.

    Raises:
        pytest.skip: If ``settings.yaml`` does not exist or has no 'test' entry.
    """
    # Import here to avoid circular imports at collection time.
    from python.utils.environments import load_env  # pylint: disable=import-outside-toplevel

    if not os.path.isfile(SETTINGS_PATH):
        pytest.skip(f'settings.yaml not found at {SETTINGS_PATH}; DB tests skipped.')

    with open(SETTINGS_PATH, 'r', encoding='utf-8') as fh:
        all_configs: dict = yaml.safe_load(fh) or {}

    if 'test' not in all_configs:
        pytest.skip("No 'test' environment in settings.yaml; DB tests skipped.")

    env = load_env('test')

    # Verify we can actually connect (e.g. GCP credentials are available)
    try:
        from python.database import sqlalchemy_main  # pylint: disable=import-outside-toplevel
        sqlalchemy_main.setup(env)
    except Exception as exc:  # pylint: disable=broad-except
        pytest.skip(f'Cannot connect to test database ({exc.__class__.__name__}); DB tests skipped.')

    yield env


@pytest.fixture(scope='session')
def clean_test_data(test_environment):
    """Delete all e2e-prefixed rows from the DB before (and after) the session.

    Deletion order respects foreign-key constraints by removing children before
    parents. No cascade deletes are assumed on the database side.

    The fixture runs cleanup both at setup (to clear stale data from previous
    interrupted runs) and at teardown (to leave the DB clean after the session).

    Args:
        test_environment: The loaded test :class:`~python.utils.environments.Environment`.

    Yields:
        None
    """
    def _do_cleanup():
        # Import lazily to avoid pulling in DB dependencies unless this fixture
        # is actually requested.
        from python.database.query import Query  # pylint: disable=import-outside-toplevel
        from python.database import models  # pylint: disable=import-outside-toplevel

        query = Query(test_environment)
        session = query.get_session()

        # --- ModelConfig / ModelRun / result tables --------------------------

        config_ids = [
            row.id for row in
            session.query(models.ModelConfig.id)
            .filter(models.ModelConfig.config_set.like('e2e_%'))
            .all()
        ]

        if config_ids:
            run_ids = [
                row.id for row in
                session.query(models.ModelRun.id)
                .filter(models.ModelRun.model_config_id.in_(config_ids))
                .all()
            ]

            if run_ids:
                session.query(models.Result).filter(
                    models.Result.model_run_id.in_(run_ids)
                ).delete(synchronize_session=False)

                session.query(models.EDES).filter(
                    models.EDES.model_run_id.in_(run_ids)
                ).delete(synchronize_session=False)

                session.query(models.PrecintDistance).filter(
                    models.PrecintDistance.model_run_id.in_(run_ids)
                ).delete(synchronize_session=False)

                session.query(models.ResidenceDistance).filter(
                    models.ResidenceDistance.model_run_id.in_(run_ids)
                ).delete(synchronize_session=False)

                session.query(models.ModelRun).filter(
                    models.ModelRun.model_config_id.in_(config_ids)
                ).delete(synchronize_session=False)

            session.query(models.ModelConfig).filter(
                models.ModelConfig.config_set.like('e2e_%')
            ).delete(synchronize_session=False)

        # --- DistanceDataSet / DistanceData ----------------------------------

        distance_set_ids = [
            row.id for row in
            session.query(models.DistanceDataSet.id)
            .filter(models.DistanceDataSet.location.like('e2e_%'))
            .all()
        ]

        if distance_set_ids:
            session.query(models.DistanceData).filter(
                models.DistanceData.distance_data_set_id.in_(distance_set_ids)
            ).delete(synchronize_session=False)

            session.query(models.DistanceDataSet).filter(
                models.DistanceDataSet.location.like('e2e_%')
            ).delete(synchronize_session=False)

        # --- DrivingDistancesSet / DrivingDistance ---------------------------

        driving_set_ids = [
            row.id for row in
            session.query(models.DrivingDistancesSet.id)
            .filter(models.DrivingDistancesSet.location.like('e2e_%'))
            .all()
        ]

        if driving_set_ids:
            session.query(models.DrivingDistance).filter(
                models.DrivingDistance.driving_distance_set_id.in_(driving_set_ids)
            ).delete(synchronize_session=False)

            session.query(models.DrivingDistancesSet).filter(
                models.DrivingDistancesSet.location.like('e2e_%')
            ).delete(synchronize_session=False)

        # --- PotentialLocationsSet / PotentialLocations ----------------------

        pl_set_ids = [
            row.id for row in
            session.query(models.PotentialLocationsSet.id)
            .filter(models.PotentialLocationsSet.location.like('e2e_%'))
            .all()
        ]

        if pl_set_ids:
            session.query(models.PotentialLocations).filter(
                models.PotentialLocations.potential_locations_set_id.in_(pl_set_ids)
            ).delete(synchronize_session=False)

            session.query(models.PotentialLocationsSet).filter(
                models.PotentialLocationsSet.location.like('e2e_%')
            ).delete(synchronize_session=False)

        session.commit()

    _do_cleanup()
    yield
    _do_cleanup()


# ---------------------------------------------------------------------------
# Shared DB import fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope='session')
def imported_potential_locations(e2e_test_data, clean_test_data, test_environment):
    """Import potential locations for the e2e session into the DB.

    Args:
        e2e_test_data: Session-scoped test data dict from :func:`e2e_test_data`.
        clean_test_data: Ensures DB is clean before and after the session.
        test_environment: The loaded test environment.

    Returns:
        None
    """
    sid = e2e_test_data['sid']
    run_cli('python.scripts.db_import_potential_locations_cli', sid, '-e', 'test')


@pytest.fixture(scope='session')
def imported_driving_distances(e2e_test_data, clean_test_data, test_environment):
    """Import driving distances for the e2e session into the DB.

    Args:
        e2e_test_data: Session-scoped test data dict from :func:`e2e_test_data`.
        clean_test_data: Ensures DB is clean before and after the session.
        test_environment: The loaded test environment.

    Returns:
        None
    """
    sid = e2e_test_data['sid']
    run_cli('python.scripts.db_import_driving_distances_cli', '2020', sid, '-e', 'test')


@pytest.fixture(scope='session')
def imported_distance_data_all(
    e2e_test_data,
    clean_test_data,
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
        clean_test_data: Ensures DB is clean before and after the session.
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
def imported_configs(e2e_test_data, clean_test_data, test_environment):
    """Import all variant config YAML files for the e2e session into the DB.

    Args:
        e2e_test_data: Session-scoped test data dict from :func:`e2e_test_data`.
        clean_test_data: Ensures DB is clean before and after the session.
        test_environment: The loaded test environment.

    Returns:
        None
    """
    config_paths = list(e2e_test_data['configs'].values())
    run_cli('python.scripts.db_import_config_cli', *config_paths, '-e', 'test')
