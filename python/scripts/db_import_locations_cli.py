'''
A command line utility to read distances into the database.
'''

from typing import List

import argparse
import os
import sys

from python.database.imports import csv_to_bigquery, ImportResult, print_all_import_results
from python.database.models import PollingLocation

from python.database import query
from python.solver.model_data import build_source
from python.utils import is_int
from python.utils.constants import LOCATION_SOURCE_DB

DEFAULT_LOG_DIR='logs'
IMPORT_ERROR_LOG_FILE='locations_import_errors.csv'

LINEAR = 'linear'
LOG = 'log'

def import_locations(
    location: str,
    polling_locations_set_id: str,
    csv_path: str,
    log: bool = False,
) -> ImportResult:
    column_renames = {
        'non-hispanic': 'non_hispanic',
    }
    ignore_columns = ['V1']
    add_columns = {
        'polling_locations_set_id': polling_locations_set_id,
    }

    return csv_to_bigquery(
        config_set=location,
        config_name=csv_path,
        model_class=PollingLocation,
        ignore_columns=ignore_columns,
        column_renames=column_renames,
        add_columns=add_columns,
        csv_path=csv_path,
        log=log,
    )


def build_and_import_locations(
    census_year: str,
    location: str,
    driving: bool,
    maps_source_date: str,
    log_distance: bool,
) -> ImportResult:

    # location_only_set = query.get_location_only_set(location)

    # if not location_only_set:
    #     raise ValueError(f'Polling location only set not found for {location}.  Please make sure it was imported.')

    # print('location_only_set --> :', location_only_set.id, '             <- :\n')

    build_source_result = build_source(
        location_source=LOCATION_SOURCE_DB,
        census_year=census_year,
        location=location,
        driving=driving,
        log_distance=log_distance,
        map_source_date=maps_source_date,
        log=False,
    )

    print('result.distance_set_id', build_source_result.distance_set_id)

    polling_locations_set = query.create_db_polling_locations_set(
        polling_locations_only_set_id=build_source_result.polling_locations_only_set_id,
        census_year=census_year,
        location=location,
        log_distance=log_distance,
        driving=driving,
        distance_set_id=build_source_result.distance_set_id,
    )

    print('polling_locations_set', polling_locations_set)

    location_path = build_source_result.output_path
    print(f'Importing {location} driving={driving} log_distance={log_distance}')
    print(f'  {location_path}')

    if not os.path.isfile(location_path):
        raise ValueError(f'File {location_path} not found')

    import_locations_result = import_locations(
        location=location,
        polling_locations_set_id=polling_locations_set.id,
        csv_path=location_path,
        log=True,
    )
    return import_locations_result


def main(args: argparse.Namespace):
    ''' Main entrypoint '''

    locations: List[str] = args.locations
    census_year: str = args.census_year[0]
    driving: bool = args.driving is not None
    if driving:
        # Use the default date for driving distances
        map_source_date = '20250101'
    else:
        map_source_date = None
    log_distance: bool = args.type == LOG

    logdir = args.logdir


    print('cencus_year:', census_year)
    print('locations:', locations)
    print('driving:', driving)
    print('map_source_date:', map_source_date)
    print('log_distance:', log_distance)

    if len(census_year) != 4 or not is_int(census_year):
        raise ValueError(f'Invalid election year {census_year}')

    num_imports = len(locations)

    print('------------------------------------------')
    print(f'Importing {num_imports} location(s)\n')


    results = []

    for i, location in enumerate(locations):
        print(f'Loading [{i+1}/{num_imports}] {location}')

        try:
            result = build_and_import_locations(
                census_year=census_year,
                location=location,
                driving=driving,
                maps_source_date=map_source_date,
                log_distance=log_distance
            )
            results.append(result)

            print('\n\n')

            query.commit()

        # pylint: disable-next=broad-exception-caught
        except Exception as e:
            result =  ImportResult(
                config_set=location,
                config_name=location,
                table_name='polling_locations',
                success=False,
                source_file=location,
                rows_written=0,
                exception=e,
            )
            results.append(result)


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
    To import linear distance haversine locations for 2020 census year for Contained_in_Madison_City_of_WI and Intersecting_Madison_City_of_WI
:
        python -m db_import_locations_cli 2020 Contained_in_Madison_City_of_WI Intersecting_Madison_City_of_WI

    To import log distance driving locations for 2020 census year for Contained_in_Madison_City_of_WI and Intersecting_Madison_City_of_WI
:
        python -m db_import_locations_cli -t log -d 20250101 2020 Contained_in_Madison_City_of_WI Intersecting_Madison_City_of_WI

       '''
    )
    parser.add_argument('-l', '--logdir', default=DEFAULT_LOG_DIR, type=str, help='The directory to error files to')
    # pylint: disable-next=line-too-long
    parser.add_argument('-t', '--type', default=LINEAR, choices=[LINEAR, LOG], help=f'The type distance to use: {LINEAR} or {LOG}')
    # pylint: disable-next=line-too-long
    # parser.add_argument('-d', '--driving', default=2025, type=str, help='Use driving distances for the specified date (YYYYMMDD)')
    # The following is temporarily used instead of the above to not require a map_source_date for
    # driving distances since this is not fully implemented yet
    # pylint: disable-next=line-too-long
    parser.add_argument('-d', '--driving', action='store_true', help='Use driving distances for the specified date (YYYYMMDD)')
    parser.add_argument('census_year', nargs=1, help='The year of the census data used to generate the distances')
    parser.add_argument('locations', nargs='+', help='One or more locations to import')

    main(parser.parse_args())

