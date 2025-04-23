'''
A command line utility to read distances into the database.
'''

import argparse
import os
import sys

from python.database.models import Distance
from python.database import query
from python.database.imports import csv_to_bigquery, ImportResult, print_all_import_results

from python.utils import is_int
from python.utils.utils import build_driving_distances_file_path

DEFAULT_LOG_DIR='logs'
IMPORT_ERROR_LOG_FILE='distance_import_errors.csv'


DISTANCE_FILE_SUFFIX = '_driving_distances.csv'

def import_distances(
    location: str,
    distance_set_id: str,
    csv_path: str,
    log: bool = False,
) -> ImportResult:
    column_renames = {}
    ignore_columns = ['V1']
    add_columns = { 'distance_set_id': distance_set_id, 'source': 'driving distance' }

    return csv_to_bigquery(
        config_set=location,
        config_name=csv_path,
        model_class=Distance,
        ignore_columns=ignore_columns,
        column_renames=column_renames,
        add_columns=add_columns,
        csv_path=csv_path,
        log=log,
    )


def main(args: argparse.Namespace):
    ''' Main entrypoint '''

    logdir = args.logdir


    locations: list[str] = args.locations
    census_year: str = args.census_year[0]

    # map_source_date: str = args.map_source_date[0]
    # Hard coded for now since map_source_date is not fully implemented
    map_source_date = '20250101'

    if len(census_year) != 4 or not is_int(census_year):
        raise ValueError(f'Invalid census year {census_year}')

    if len(map_source_date) != 8 or not is_int(census_year):
        raise ValueError(f'Invalid maps source date {map_source_date}')

    num_imports = len(locations)


    print('------------------------------------------')
    print(f'Importing {num_imports} location(s)\n')


    results = []

    for i, location in enumerate(locations):
        distance_file_path = build_driving_distances_file_path(census_year, map_source_date, location)

        print(f'Loading [{i+1}/{num_imports}] {distance_file_path}')


        distance_set = query.create_db_distance_set(census_year, map_source_date, location)

        print(f'Importing distances from {distance_set}')

        import_distances_result = import_distances(
            location=location,
            distance_set_id=distance_set.id,
            csv_path=distance_file_path,
        )

        # print('\n\n')

        query.commit()

        results.append(import_distances_result)


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
        # pylint: disable-next=line-too-long
        description='A command line utility to read in distance csv files and import them into the database.',
        epilog='''
Examples:
    To import distance file for 2020 census year for Contained_in_Madison_City_of_WI_driving_distances.csv:
ß
        python -m db_import_distances_cli 2020 Contained_in_Madison_City_of_WI
        '''
    )
    parser.add_argument('census_year', nargs=1, help='The year of the census data used to generate the distances')
    # Removed since map_source_date is not fully implemented
    # parser.add_argument('map_source_date', nargs=1, help='The date (YYYYMMDD) of the map data used to generate the distances')
    parser.add_argument('locations', nargs='+', help='One or more locations to import for the specifed census year and map date')
    parser.add_argument('-l', '--logdir', default=DEFAULT_LOG_DIR, type=str, help='The directory to error files to ')

    main(parser.parse_args())

