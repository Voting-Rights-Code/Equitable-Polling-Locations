'''
A command line utility to read polling location only files into the database.
'''

from typing import List

import argparse
import os
import sys

from python.database.imports import csv_to_bigquery, ImportResult, print_all_import_results
from python.database.models import (
    PollingLocationOnly,
)

from python.database.query import Query
from python.utils.environments import Environment, load_env
from python.utils.utils import build_locations_only_file_path

DEFAULT_LOG_DIR='logs'
IMPORT_ERROR_LOG_FILE='locations_only_import_errors.csv'


def import_locations_only(
    environment: Environment,
    location: str,
    polling_locations_only_set_id: str,
    csv_path: str,
    log: bool = False,
) -> ImportResult:

    column_renames = {
        'Location': 'location',
        'Address': 'address',
        'Location type': 'location_type',
        'Lat, Long': 'lat_lon',
    }
    ignore_columns = ['V1', 'Latitude', 'Longitude']
    add_columns = {
        'polling_locations_only_set_id': polling_locations_only_set_id
    }

    return csv_to_bigquery(
        environment=environment,
        config_set=location,
        config_name=csv_path,
        model_class=PollingLocationOnly,
        ignore_columns=ignore_columns,
        column_renames=column_renames,
        add_columns=add_columns,
        csv_path=csv_path,
        log=log,
    )

def main(args: argparse.Namespace):
    ''' Main entrypoint '''

    logdir = args.logdir
    locations: List[str] = args.locations
    environment = load_env(args.environment)

    num_imports = len(locations)

    print('------------------------------------------')
    print(f'Importing {num_imports} location(s) into {environment}\n')


    results = []

    for i, location in enumerate(locations):
        query = Query(environment)

        print(f'Loading [{i+1}/{num_imports}] {location}')

        locations_only_file_path = build_locations_only_file_path(location)
        print('locations_only_file_path:', locations_only_file_path)

        if not os.path.isfile(locations_only_file_path):
            print(f'Locations only file not found: {locations_only_file_path}')
            continue

        polling_locations_only_set = query.create_db_polling_locations_only_set(
            location=location,
        )

        import_locations_only_result = import_locations_only(
            environment=environment,
            location=location,
            polling_locations_only_set_id=polling_locations_only_set.id,
            csv_path=locations_only_file_path,
            log=True,
        )
        results.append(import_locations_only_result)

        query.commit()


    success_results = [ result for result in results if result.success ]
    failed_results = [ result for result in results if not result.success ]

    num_successes = len(success_results)
    num_failures = len(failed_results)

    print('--------')
    print(f'\nSuccesses ({num_successes}):')
    print_all_import_results(success_results)
    print(f'\n\nFailures ({num_failures}):')
    print_all_import_results(failed_results)

    # Write any errors to the log dir
    log_path = os.path.join(os.getcwd(), logdir)
    if not os.path.exists(log_path):
        os.makedirs(logdir)
    output_path = os.path.join(log_path, IMPORT_ERROR_LOG_FILE)
    print_all_import_results(failed_results, output_path=output_path)

    if num_failures:
        sys.exit(10)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='A command line utility to read in location csv files and import them into the database.',
        # pylint: disable-next=line-too-long
        epilog='''
Examples:
    To import locations only for Contained_in_Madison_City_of_WI and Intersecting_Madison_City_of_WI
:

        python ./db_import_locations_only_cli.py Contained_in_Madison_City_of_WI Intersecting_Madison_City_of_WI
        '''
    )
    parser.add_argument('-e', '--environment', type=str, help='The environment to use')
    parser.add_argument('-l', '--logdir', default=DEFAULT_LOG_DIR, type=str, help='The directory to error files to ')
    parser.add_argument('locations', nargs='+', help='One or more locations only to import')

    main(parser.parse_args())

