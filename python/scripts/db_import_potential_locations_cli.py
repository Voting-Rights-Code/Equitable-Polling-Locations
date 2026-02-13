'''
A command line utility to read polling location only files into the database.
'''

from typing import List

import argparse
import os
import sys

from python.database.imports import csv_to_bigquery, ImportResult, print_all_import_results
from python.database.models import (
    PotentialLocations,
)

from python.database.query import Query
from python.utils.environments import Environment, load_env
from python.utils.utils import build_potential_locations_file_path

from python.solver.constants import (
    POT_LOC_LOCATION,
    POT_LOC_ADDRESS,
    POT_LOC_LOCATION_TYPE,
    POT_LOC_LAT_LON,
    POT_LOC_LATITUDE,
    POT_LOC_LONGITUDE,
)

DEFAULT_LOG_DIR='logs'
IMPORT_ERROR_LOG_FILE='potential_locations_import_errors.csv'


def import_potential_locations(
    environment: Environment,
    location: str,
    potential_locations_set_id: str,
    csv_path: str,
    log: bool = False,
) -> ImportResult:

    column_renames = {
        POT_LOC_LOCATION: 'location',
        POT_LOC_ADDRESS: 'address',
        POT_LOC_LOCATION_TYPE: 'location_type',
        POT_LOC_LAT_LON: 'lat_lon',
    }
    ignore_columns = ['V1', POT_LOC_LATITUDE, POT_LOC_LONGITUDE]
    add_columns = {
        'potential_locations_set_id': potential_locations_set_id
    }

    return csv_to_bigquery(
        environment=environment,
        config_set=location,
        config_name=csv_path,
        model_class=PotentialLocations,
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
    print(f'Importing {num_imports} potential location(s) into {environment}\n')


    results = []

    for i, location in enumerate(locations):
        query = Query(environment)

        print(f'Loading [{i+1}/{num_imports}] {location}')

        potential_locations_file_path = build_potential_locations_file_path(location)
        print('potential_locations_file_path:', potential_locations_file_path)

        if not os.path.isfile(potential_locations_file_path):
            print(f'Potential locations file not found: {potential_locations_file_path}')
            continue

        potential_locations_set = query.create_db_potential_locations_set(
            location=location,
        )

        import_potential_locations_result = import_potential_locations(
            environment=environment,
            location=location,
            potential_locations_set_id=potential_locations_set.id,
            csv_path=potential_locations_file_path,
            log=True,
        )
        results.append(import_potential_locations_result)

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
        description='A command line utility to read in potential location csv files and import them into the database.',
        # pylint: disable-next=line-too-long
        epilog='''
Examples:
    To import locations only for Contained_in_Madison_City_of_WI and Intersecting_Madison_City_of_WI
:

        python -m python.scripts.db_import_potential_locations_cli Contained_in_Madison_City_of_WI Intersecting_Madison_City_of_WI
        '''
    )
    parser.add_argument('-e', '--environment', type=str, help='The environment to use')
    parser.add_argument('-l', '--logdir', default=DEFAULT_LOG_DIR, type=str, help='The directory to error files to ')
    parser.add_argument('locations', nargs='+', help='One or more potential locations to import')

    main(parser.parse_args())

