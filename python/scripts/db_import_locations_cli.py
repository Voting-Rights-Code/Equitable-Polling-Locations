'''
A command line utility to read distances into the database.
'''

from typing import List, Tuple

import argparse
import os
import sys

import pandas as pd

from python.database.imports import csv_to_bigquery, ImportResult
from python.database.models import (
    LOCATION_TYPE_CITY,
    LOCATION_TYPE_COUNTY,
    LOCATION_TYPE_CONTAINED_IN_CITY,
    LOCATION_TYPE_INTERSECTING_CITY,
    PollingLocation,
    PollingLocationOnly,
)

from python.database import query
from python.solver.model_data import build_source
from python.utils import is_int
from python.utils.utils import build_locations_only_file_path

DEFAULT_LOG_DIR='logs'
IMPORT_ERROR_LOG_FILE='locations_import_errors.csv'

HAVERSINE = 'haversine'
DRIVING = 'driving'
ALL = 'ALL'

def import_locations(
    location: str,
    polling_locations_set_id: str,
    csv_path: str,
    driving: bool,
    log_distance: bool,
    log: bool = False,
) -> ImportResult:
    column_renames = {
        'non-hispanic': 'non_hispanic',
    }
    ignore_columns = ['V1']
    add_columns = {
        'polling_locations_set_id': polling_locations_set_id,
        'log_distance': log_distance,
        'driving': driving,
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

def import_locations_only(
    name: str,
    polling_locations_set_id: str,
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
        'polling_locations_set_id': polling_locations_set_id
    }

    return csv_to_bigquery(
        config_set=name,
        config_name=csv_path,
        model_class=PollingLocationOnly,
        ignore_columns=ignore_columns,
        column_renames=column_renames,
        add_columns=add_columns,
        csv_path=csv_path,
        log=log,
    )


def print_all_import_results(import_results_list: List[ImportResult], output_path: str=None):
    ''' Prints to the screen a summary of all import results. '''

    data = {
        'timestamp': [ r.timestamp for r in import_results_list ],
        'config_set': [ r.config_set for r in import_results_list ],
        'config_name': [ r.config_name for r in import_results_list ],
        'success': [ r.success for  r in import_results_list ],
        'table_name': [ r.table_name for r in import_results_list ],
        'source_file': [ r.source_file for r in import_results_list ],
        'rows_written': [ r.rows_written for  r in import_results_list ],
        'error': [ str(r.exception or '') for  r in import_results_list ],
    }

    df = pd.DataFrame(data)
    if output_path:
        # Write to a file

        if os.path.exists(output_path):
            mode = 'a'
            header = False
        else:
            mode = 'w'
            header = True
        df.to_csv(output_path, mode=mode, header=header, index=False)
    else:
        # Write to the screen
        print(df.to_csv(index=False))



def parse_polling_location_directory_name(location_directory: str) -> Tuple[str, str, str]:
    ''' Returns the state, location type, and location from a distance csv filename as a tuple '''

    # Get the file name without the path
    name = os.path.basename(location_directory).lower()

    name_parts = name.split('_')

    if len(name_parts) < 3:
        raise ValueError(f'Invalid polling location path {location_directory}, not enough parts in name')

    state = name_parts.pop().lower()
    if len(state) != 2:
        raise ValueError(f'Invalid distance file path {location_directory}, state {state} is not 2 characters')

    if '_city_' in name:
        if 'contained_in' in name:
            location_type = LOCATION_TYPE_CONTAINED_IN_CITY
        elif 'intersecting' in name:
            location_type = LOCATION_TYPE_INTERSECTING_CITY
        else:
            location_type = LOCATION_TYPE_CITY
    elif '_county_' in name:
        location_type = LOCATION_TYPE_COUNTY
    else:
        raise ValueError(f'Invalid polling location path {location_directory}, location type not found')

    # For now the location will just be the directory name
    location = name

    return (state, location_type, location)

def build_and_import_locations(
    polling_locations_set_id: str,
    location: str,
    driving: bool,
    log_distance: bool,
) -> ImportResult:
    location_path = build_source(location, driving, log_distance, log=False)
    print(f'Importing {location} driving={driving} log_distance={log_distance}')
    print(f'  {location_path}')

    if not os.path.isfile(location_path):
        raise ValueError(f'File {location_path} not found')

    import_locations_result = import_locations(
        location=location,
        polling_locations_set_id=polling_locations_set_id,
        csv_path=location_path,
        driving=driving,
        log_distance=log_distance,
        log=True,
    )
    return import_locations_result


def main(args: argparse.Namespace):
    ''' Main entrypoint '''

    logdir = args.logdir
    distance_type: str = args.type or ALL
    locations: List[str] = args.locations

    print('distance_type', distance_type)

    election_year: str = args.election_year[0]

    if len(election_year) != 4 or not is_int(election_year):
        raise ValueError(f'Invalid election year {election_year}')

    num_imports = len(locations)

    print('------------------------------------------')
    print(f'Importing {num_imports} location(s)\n')


    results = []

    for i, location in enumerate(locations):
        print(f'Loading [{i+1}/{num_imports}] {location}')

        locations_only_file_path = build_locations_only_file_path(location)
        print('locations_only_file_path:', locations_only_file_path)

        if not os.path.isfile(locations_only_file_path):
            print('Locations only file not found: {locations_only_file_path}')
            continue

        polling_locations_set = query.create_db_polling_locations_set(
            location=location,
            election_year=election_year,
        )

        import_locations_only_result = import_locations_only(
            name=location,
            polling_locations_set_id=polling_locations_set.id,
            csv_path=locations_only_file_path,
            log=True,
        )
        results.append(import_locations_only_result)

        try:
            if (distance_type == ALL) or (distance_type == DRIVING):
                result = build_and_import_locations(
                    polling_locations_set.id,
                    location,
                    driving=True,
                    log_distance=False
                )
                results.append(result)

                result = build_and_import_locations(
                    polling_locations_set.id,
                    location,
                    driving=True,
                    log_distance=True
                )
                results.append(result)

            if distance_type == ALL or distance_type == HAVERSINE:
                result = build_and_import_locations(
                    polling_locations_set.id,
                    location,
                    driving=False,
                    log_distance=False
                )
                results.append(result)

                result = build_and_import_locations(
                    polling_locations_set.id,
                    location,
                    driving=False,
                    log_distance=True
                )
                results.append(result)


            print('\n\n')

            query.commit()

        # pylint: disable-next=broad-exception-caught
        except Exception as e:
            print("Exception:", e)
            result =  ImportResult(
                config_set=location,
                config_name=location,
                table_name='polling_locations',
                success=False,
                source_file=location,
                rows_written=0,
                exception=e,
            )


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
    To import locations for Contained_in_Madison_City_of_WI and Intersecting_Madison_City_of_WI
:

        python ./db_import_locations_cli.py Contained_in_Madison_City_of_WI Intersecting_Madison_City_of_WI
        '''
    )
    parser.add_argument('-l', '--logdir', default=DEFAULT_LOG_DIR, type=str, help='The directory to error files to ')
    parser.add_argument('-t', '--type', default=ALL, choices=[ALL, HAVERSINE, DRIVING], help='The type of location to import: haversine, driving, or all for both')
    parser.add_argument('election_year', nargs=1, help='The year of the census data used to generate the distances')
    parser.add_argument('locations', nargs='+', help='One or location directories with csv location files to import')

    main(parser.parse_args())

