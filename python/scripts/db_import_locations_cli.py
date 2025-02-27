'''
A command line utility to read distances into the database.
'''

from typing import List, Tuple

import argparse
from glob import glob
import os


import pandas as pd
from python.database.imports import ImportResult
from python.database.models import (
    LOCATION_TYPE_CITY,
    LOCATION_TYPE_COUNTY,
    LOCATION_TYPE_CONTAINED_IN_CITY,
    LOCATION_TYPE_INTERSECTING_CITY,
    PollingLocation,
    PollingLocationOnly,
)

from python.database import query
from python.utils import is_int


# MODEL_RUN_ID = 'model_run_id'

# RESULTS_PATH = 'results_path'
# PRECINCT_DISTANCES_PATH = 'precinct_distances_path'
# RESIDENCE_DISTANCES_PATH = 'residence_distances_path'
# EDE_PATH = 'EDE_PATH'

DEFAULT_LOG_DIR='logs'
IMPORT_ERROR_LOG_FILE='distance_import_errors.csv'


DISTANCE_FILE_SUFFIX = '_driving_distances.csv'

def import_locations(
    name: str,
    polling_locations_set_id: str,
    csv_path: str,
    log: bool = False,
) -> ImportResult:

    column_renames = {
        'non-hispanic': 'non_hispanic',
    }
    ignore_columns = ['V1']
    add_columns = { 'polling_locations_set_id': polling_locations_set_id }

    return query.csv_to_bigquery(
        config_set=name,
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
) -> query.ImportResult:

    column_renames = {
        'Location': 'location',
        'Address': 'address',
        'Location type': 'location_type',
        'Lat, Long': 'lat_lon',
    }
    ignore_columns = ['V1']
    add_columns = {
        'polling_locations_set_id': polling_locations_set_id
    }

    return query.csv_to_bigquery(
        config_set=name,
        config_name=csv_path,
        model_class=PollingLocationOnly,
        ignore_columns=ignore_columns,
        column_renames=column_renames,
        add_columns=add_columns,
        csv_path=csv_path,
        log=log,
    )


# def import_edes(
#         config_set: str,
#         config_name: str,
#         model_run_id: str,
#         csv_path: str = None,
#         df: pd.DataFrame = None,
#         log: bool = False,
# ) -> query.ImportResult:
#     ''' Imports an existing EDEs csv into the database for a given mode_run_id. '''

#     column_renames = {}
#     ignore_columns = ['V1']
#     add_columns = { 'model_run_id': model_run_id }

#     return query.csv_to_bigquery(
#         config_set=config_set,
#         config_name=config_name,
#         model_class=Models.EDES,
#         ignore_columns=ignore_columns,
#         column_renames=column_renames,
#         add_columns=add_columns,
#         csv_path=csv_path,
#         df=df,
#         log=log,
#     )

def print_all_import_results(import_results_list: List[query.ImportResult], output_path: str=None):
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

def build_locations_only_file_path(location_directory: str) -> str:
    ''' Builds the expected file path for the locations only csv file. '''

    dirname = os.path.basename(location_directory)

    filename = f'{dirname}_locations_only.csv'

    return os.path.join(location_directory, filename)

def build_locations_file_path(location_directory: str) -> str:
    ''' Builds the expected file path for the locations csv file. '''

    dirname = os.path.basename(location_directory)

    filename = f'{dirname}.csv'

    return os.path.join(location_directory, filename)


def main(args: argparse.Namespace):
    ''' Main entrypoint '''

    logdir = args.logdir

    election_year: str = args.election_year[0]

    if len(election_year) != 4 or not is_int(election_year):
        raise ValueError(f'Invalid election year {election_year}')

    glob_paths = [ glob(item) for item in args.location_directories ]
    location_directories: List[str] = [ item for sublist in glob_paths for item in sublist ]

    for location_directory in location_directories:
        if not os.path.isdir(location_directory):
            raise ValueError(f'Invalid location path {location_directory}')

    num_imports = len(location_directories)

    print('------------------------------------------')
    print(f'Importing {num_imports} location(s)\n')


    results = []

    for i, location_directory in enumerate(location_directories):
        success = True
        print(f'Loading [{i+1}/{num_imports}] {location_directory}')

        locations_only_path = build_locations_only_file_path(location_directory)
        locations_path = build_locations_file_path(location_directory)
        state, location_type, location = parse_polling_location_directory_name(location_directory)

        print(f'Locations only path: {locations_only_path}')
        print(f'Locations path: {locations_path}')
        print(state, location_type, location)

        polling_locations_set = query.create_db_polling_locations_set(state, location_type, location, election_year)

        print(f'Importing polling locations from {polling_locations_set}')

        import_locations_result = []

        if not os.path.isfile(locations_only_path):
            raise ValueError(f'Locations only file not found: {locations_only_path}')

        if os.path.isfile(locations_path):
            import_locations_result = import_locations(
                name=location,
                polling_locations_set_id=polling_locations_set.id,
                csv_path=locations_path,
                log=True,
            )

        import_locations_only_result = import_locations_only(
            name=location,
            polling_locations_set_id=polling_locations_set.id,
            csv_path=locations_only_path,
            log=True,
        )

        # print('\n\n')

        query.commit()

        results.append(import_locations_only_result)
        results.append(import_locations_result)


    # success_results = [ result for result in results if result.success ]
    # failed_results = [ result for result in results if not result.success ]

    # num_successes = len(success_results)
    # num_failures = len(failed_results)

    # print('--------')
    # print(f'\nSuccesses ({num_successes}):')
    # print_all_import_results(success_results)
    # print(f'\n\nFailures ({num_failures}):')
    # print_all_import_results(failed_results)

    # # Write any errors to the log dir
    # log_path = os.path.join(os.getcwd(), logdir)
    # if not os.path.exists(log_path):
    #     os.makedirs(logdir)
    # output_path = os.path.join(log_path, IMPORT_ERROR_LOG_FILE)
    # print_all_import_results(failed_results, output_path=output_path)

    # if num_failures:
    #     sys.exit(10)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        # pylint: disable-next=line-too-long
        description='A command line utility to read in location csv files and import them into the database.',
        epilog='''
Examples:
    To import all model data location file named Contained_in_Madison_City_of_WI_driving_distances.csv:

        python ./db_import_distances_cli.py ../datasets/driving/Contained_in_Madison_City_of_WI/Contained_in_Madison_City_of_WI_driving_distances.csv
        '''
    )
    parser.add_argument('election_year', nargs=1, help='The year of the census data used to generate the distances')
    parser.add_argument('location_directories', nargs='+', help='One or location directories with csv location files to import')
    parser.add_argument('-l', '--logdir', default=DEFAULT_LOG_DIR, type=str, help='The directory to error files to ')

    main(parser.parse_args())

