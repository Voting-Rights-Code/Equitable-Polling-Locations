'''
One-off backfill script for the Tarrant County DB upload (2026-08-29).

What this does, and why it isn't just the existing CLIs:

1. Distance data (2 uploads): db_import_distance_data_cli.py always *recomputes* the
   distance matrix from scratch and overwrites the local CSV before uploading it -- it
   has no "just upload this existing file" mode. Both Tarrant distance CSVs on disk
   already contain valid, previously-computed data (one pre-2026, one current), so this
   script uploads each file's existing content directly, explicitly linked to the correct
   potential_locations_set for its vintage (not "most recently created", which is what
   the normal build path would silently pick -- see the linked issue for why that
   resolution is ambiguous once multiple vintages exist for one location).

2. Configs + runs (6 backfills): db_import_cli.py hardcodes distance_data_set_id=None
   for any non-driving config (all of ours), and hardcodes username='chad'. This
   reproduces an orphaned-provenance problem (a config/run with no real link to the
   distance data it was solved against). This script does the same config-find-or-create
   + model_run + 4-CSV-import as db_import_cli.py, but threads through an explicit
   distance_data_set_id (2025-vintage set for 5 configs, 2026-vintage set for the
   year_2026 config) and uses username='' (matching the convention used by the normal
   solver-driven DB write path in model_results.py).

Uses the already-solved local result CSVs -- no solver re-run (expensive: up to 40GB RAM,
time_limit=360000s per config).

MEMORY REQUIREMENT: uploading a full-size distance CSV (~7GB for Tarrant) requires
reading the whole file into a pandas DataFrame before BigQuery's client library will
upload it (see upload_distance_data / bigquery_bluk_insert_dataframe in
python/database/imports.py, which calls client.load_table_from_dataframe -- there is no
streaming-from-disk path). On an 8GB-RAM machine this thrashes swap for hours without
completing. Run this on a machine with meaningfully more RAM than the CSV's size (16GB+
recommended for a ~7GB file) -- see the linked issue for details and a possible longer-term
fix (a streaming/chunked upload, or shelling out to `bq load` directly instead of pandas).

Defaults to the `test` environment (tests_chad dataset, same project/schema as prod, just
a scratch dataset) -- pass --environment prod to run for real. In test mode, the two
hardcoded prod potential_locations_set ids don't exist, so fresh placeholder sets are
created instead (fine for a plumbing smoke test -- the distance upload never reads
potential_locations rows, it just stamps the id onto the distance_data_set row). Use
--sample-rows N in test mode to upload only the first N rows of each distance CSV instead
of the full multi-GB file.

Each distance upload and each config backfill is wrapped independently (its own Query,
its own try/except+rollback) so one failure -- e.g. a timeout on the multi-GB distance
upload -- doesn't stop the others from running.
'''

import argparse
import os
import sys

import pandas as pd

from python.database.query import Query
from python.database.imports import print_all_import_results, import_edes, import_results, \
    import_precinct_distances, import_residence_distances
from python.solver.model_config import PollingModelConfig
from python.utils import current_time_utc
from python.utils.directory_constants import DATASETS_DIR, CONFIG_BASE_DIR
from python.utils.environments import load_env
from python.scripts.db_import_cli import output_file_paths, RESULTS_PATH, PRECINCT_DISTANCES_PATH, \
    RESIDENCE_DISTANCES_PATH, EDE_PATH
from python.scripts.db_import_distance_data_cli import import_distance_data

LOCATION = 'Tarrant_County_TX'
CENSUS_YEAR = '2020'

# Resolved 2026-08-29 against the prod potential_locations table -- see the linked issue.
# Only valid in the real prod dataset; test mode creates its own placeholder sets instead.
PROD_POTENTIAL_LOCATIONS_SET_2025 = '1946f655-4864-4f8a-8b1e-531d875fee15'  # 368 rows, pre-2026
PROD_POTENTIAL_LOCATIONS_SET_2026 = '8924637d-2177-43db-9755-2349c8729248'  # 372 rows, current

DISTANCE_CSV_2025 = os.path.join(
    DATASETS_DIR, 'polling', LOCATION,
    f'{LOCATION}_distances_{CENSUS_YEAR}_log.csv.db-upload-in-progress.bak',
)
DISTANCE_CSV_2026 = os.path.join(
    DATASETS_DIR, 'polling', LOCATION, f'{LOCATION}_distances_{CENSUS_YEAR}_log.csv',
)

# (config path, vintage label) -- vintage determines which distance_data_set the
# resulting model_run links to. This is everything tagged "2025" in the reviewed
# inventory except Tarrant_County_TX_fair (capacity 1.2, "cannot be run, do not
# upload"), plus the single "2026" config that already has a complete local result set.
CONFIG_BACKFILLS = [
    (os.path.join(CONFIG_BASE_DIR, f'{LOCATION}_original_configs', f'{LOCATION}_year_2024.yaml'), '2025'),
    (os.path.join(CONFIG_BASE_DIR, f'{LOCATION}_original_configs', f'{LOCATION}_year_2025.yaml'), '2025'),
    (os.path.join(CONFIG_BASE_DIR, f'{LOCATION}_original_configs_capacity_2', f'{LOCATION}_year_2024.yaml'), '2025'),
    (os.path.join(CONFIG_BASE_DIR, f'{LOCATION}_original_configs_capacity_2', f'{LOCATION}_year_2025.yaml'), '2025'),
    (os.path.join(CONFIG_BASE_DIR, f'{LOCATION}_fair_capacity_2', f'{LOCATION}_precincts_open_215.yaml'), '2025'),
    (os.path.join(CONFIG_BASE_DIR, f'{LOCATION}_original_configs_capacity_2', f'{LOCATION}_year_2026.yaml'), '2026'),
]


def make_sample_csv(source_path, sample_rows):
    ''' Writes the first sample_rows data rows of source_path to a temp file and returns
    its path. Only used in test mode, to avoid uploading the full multi-GB file. '''
    sample_df = pd.read_csv(source_path, nrows=sample_rows)
    sample_path = f'/tmp/{os.path.basename(source_path)}.sample_{sample_rows}.csv'
    sample_df.to_csv(sample_path, index=False)
    return sample_path


def get_potential_locations_set_id(query, environment_name, prod_set_id):
    '''
    In prod, use the already-resolved real set id. In any other environment (e.g. test),
    that id won't exist, so create a fresh placeholder set instead -- fine for a
    plumbing/smoke test since uploading distance data doesn't read potential_locations
    rows, it just stamps the id onto the new distance_data_set row.
    '''
    if environment_name == 'prod':
        return prod_set_id

    placeholder = query.create_db_potential_locations_set(location=LOCATION)
    placeholder_id = placeholder.id  # capture before commit -- BigQuery can't refresh expired attributes
    query.commit()
    print(f'[{environment_name}] created placeholder potential_locations_set {placeholder_id} (not the real prod set)')
    return placeholder_id


def upload_distance_data(query, potential_locations_set_id, csv_path):
    '''
    Creates a distance_data_set row linked to the given potential_locations_set, then
    uploads the existing (already-computed) CSV directly to BigQuery -- no recompute.
    '''
    distance_data_set = query.create_db_distance_data_set(
        potential_locations_set_id=potential_locations_set_id,
        census_year=CENSUS_YEAR,
        location=LOCATION,
        log_distance=True,
        driving=False,
        driving_distance_set_id=None,
    )

    distance_data_set_id = distance_data_set.id  # capture before commit -- BigQuery can't refresh expired attributes
    print(f'Created distance_data_set {distance_data_set_id} -> potential_locations_set {potential_locations_set_id}')

    result = import_distance_data(
        environment=query.environment,
        location=LOCATION,
        distance_data_set_id=distance_data_set_id,
        csv_path=csv_path,
        log=True,
    )

    query.commit()

    return distance_data_set_id, result


def backfill_config_and_run(query, config_path, distance_data_set_id):
    '''
    Imports a config (find-or-create, no duplicate) plus a new model_run and its 4
    result CSVs from the existing local results, explicitly linked to
    distance_data_set_id.
    '''
    config_source = PollingModelConfig.load_config(config_path)
    paths = output_file_paths(config_source)

    db_model_config = query.create_db_model_config(config_source)
    model_config = query.find_or_create_model_config(db_model_config, log=True)

    model_run = query.create_model_run(
        model_config_id=model_config.id,
        distance_data_set_id=distance_data_set_id,
        username='',
        commit_hash='',
        created_at=current_time_utc(),
    )

    config_set = model_config.config_set
    config_name = model_config.config_name

    print(f'Backfilling {config_set}/{config_name} -> model_run {model_run.id}')

    import_results_list = [
        import_edes(query.environment, config_set, config_name, model_run.id, csv_path=paths[EDE_PATH], log=True),
        import_results(
            query.environment, config_set, config_name, model_run.id, csv_path=paths[RESULTS_PATH], log=True,
        ),
        import_precinct_distances(
            query.environment, config_set, config_name, model_run.id,
            csv_path=paths[PRECINCT_DISTANCES_PATH], log=True,
        ),
        import_residence_distances(
            query.environment, config_set, config_name, model_run.id,
            csv_path=paths[RESIDENCE_DISTANCES_PATH], log=True,
        ),
    ]

    model_run.success = all(result.success for result in import_results_list)

    query.commit()

    return import_results_list


def run_distance_uploads(environment, environment_name, sample_rows):
    ''' Uploads both distance CSVs independently; a failure in one does not prevent the
    other from being attempted. Returns {vintage_label: distance_data_set_id or None}. '''
    all_results = []
    distance_set_ids = {}

    for label, prod_potential_locations_set_id, csv_path in [
        ('2025', PROD_POTENTIAL_LOCATIONS_SET_2025, DISTANCE_CSV_2025),
        ('2026', PROD_POTENTIAL_LOCATIONS_SET_2026, DISTANCE_CSV_2026),
    ]:
        query = Query(environment)
        try:
            potential_locations_set_id = get_potential_locations_set_id(
                query, environment_name, prod_potential_locations_set_id,
            )
            upload_path = csv_path if not sample_rows else make_sample_csv(csv_path, sample_rows)
            distance_data_set_id, result = upload_distance_data(query, potential_locations_set_id, upload_path)
            all_results.append(result)
            distance_set_ids[label] = distance_data_set_id if result.success else None
            if not result.success:
                print(f'Distance upload for {label} reported failure -- dependent configs will be skipped.')
        # pylint: disable-next=broad-exception-caught
        except Exception as e:
            query.rollback()
            print(f'Distance upload for {label} raised an exception, skipping: {e}')
            distance_set_ids[label] = None

    return distance_set_ids, all_results


def run_config_backfills(environment, distance_set_ids):
    ''' Backfills each config independently; a failure in one does not prevent the others
    from being attempted. Configs whose vintage's distance upload failed are skipped. '''
    all_results = []

    for config_path, vintage_label in CONFIG_BACKFILLS:
        distance_data_set_id = distance_set_ids.get(vintage_label)
        if not distance_data_set_id:
            print(f'Skipping {config_path} -- no successful {vintage_label} distance_data_set to link to.')
            continue

        query = Query(environment)
        try:
            import_results_list = backfill_config_and_run(query, config_path, distance_data_set_id)
            all_results.extend(import_results_list)
        # pylint: disable-next=broad-exception-caught
        except Exception as e:
            query.rollback()
            print(f'Backfill for {config_path} raised an exception, skipping: {e}')
        print()

    return all_results


def main():
    parser = argparse.ArgumentParser(description='One-off Tarrant County DB backfill.')
    parser.add_argument(
        '-e', '--environment', default='test', choices=['test', 'prod'],
        help='Defaults to "test" (tests_chad dataset, scratch). Pass --environment prod to run for real.',
    )
    parser.add_argument(
        '--sample-rows', type=int, default=None,
        help='Test mode only: upload only the first N rows of each distance CSV instead of the full file.',
    )
    args = parser.parse_args()

    if args.sample_rows and args.environment == 'prod':
        print('Refusing to run a sampled upload against prod -- --sample-rows is for test mode only.')
        sys.exit(1)

    environment = load_env(args.environment)

    print(f'=== Step 1: distance data (environment={args.environment}) ===\n')
    distance_set_ids, distance_results = run_distance_uploads(environment, args.environment, args.sample_rows)

    print('\n=== Step 2: configs + runs ===\n')
    config_results = run_config_backfills(environment, distance_set_ids)

    all_results = distance_results + config_results
    success_results = [result for result in all_results if result.success]
    failed_results = [result for result in all_results if not result.success]

    print('--------')
    print(f'\nSuccesses ({len(success_results)}):')
    print_all_import_results(success_results)
    print(f'\n\nFailures ({len(failed_results)}):')
    print_all_import_results(failed_results)

    if failed_results:
        sys.exit(10)


if __name__ == '__main__':
    main()
