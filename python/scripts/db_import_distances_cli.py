'''
A command line utility to read distances into the database.
'''

from typing import List, Tuple

import argparse
from glob import glob
import os
import sys


import pandas as pd

from python.database.models import LOCATION_TYPE_CITY, LOCATION_TYPE_COUNTY, Distance
from python.database import query
from python.database.imports import csv_to_bigquery, ImportResult

# from python.solver.model_config import PollingModelConfig
from python.utils import is_int
#build_precinct_summary_file_path, build_residence_summary_file_path,
# # build_results_file_path, build_y_ede_summary_file_path, current_time_utc
# from python.utils.constants import DATASETS_DIR, RESULTS_BASE_DIR

# MODEL_RUN_ID = 'model_run_id'

# RESULTS_PATH = 'results_path'
# PRECINCT_DISTANCES_PATH = 'precinct_distances_path'
# RESIDENCE_DISTANCES_PATH = 'residence_distances_path'
# EDE_PATH = 'EDE_PATH'

DEFAULT_LOG_DIR='logs'
IMPORT_ERROR_LOG_FILE='distance_import_errors.csv'


DISTANCE_FILE_SUFFIX = '_driving_distances.csv'

def import_distances(
    state: str,
    location_type: str,
    location: str,
    distance_set_id: str,
    csv_path: str,
    log: bool = False,
) -> ImportResult:

    column_renames = {}
    ignore_columns = ['V1']
    add_columns = { 'distance_set_id': distance_set_id }

    import_name = f'{location_type}_{location}_{state}'

    return csv_to_bigquery(
        config_set=import_name,
        config_name=csv_path,
        model_class=Distance,
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



def parse_distance_filename(distance_file_path: str) -> Tuple[str, str, str]:
    ''' Returns the state, location type, and location from a distance csv filename as a tuple '''
    if not distance_file_path or not distance_file_path.endswith(DISTANCE_FILE_SUFFIX):
        raise ValueError(f'Invalid distance file path {distance_file_path}')

    # Get the file name without the path
    name = os.path.basename(distance_file_path)

    # Strip off the _driving_distances.csv
    name = name[:-len(DISTANCE_FILE_SUFFIX)]

    name_parts = name.split('_')

    # Make sure the name contains at least 3 parts for the location type, county, and state
    if len(name_parts) < 3:
        raise ValueError(f'Invalid distance file path {distance_file_path}, not enough parts in name')

    # get the state by remove the right-most section of the split file and removing the .csv part
    state = name_parts.pop().lower()
    if len(state) != 2:
        raise ValueError(f'Invalid distance file path {distance_file_path}, state {state} is not 2 characters')

    # get the location type by removing the right-most section of the split file
    location_type = name_parts.pop().lower()
    if location_type not in [LOCATION_TYPE_CITY, LOCATION_TYPE_COUNTY]:
        raise ValueError(f'Invalid distance file path {distance_file_path}, location type {location_type} is not valid')

    # The rest of the name is the county
    location = ' '.join(name_parts).lower()

    return (state, location_type, location)


def main(args: argparse.Namespace):
    ''' Main entrypoint '''

    logdir = args.logdir

    census_year: str = args.census_year[0]
    map_source_year: str = args.map_source_year[0]

    if len(census_year) != 4 or not is_int(census_year):
        raise ValueError(f'Invalid census year {census_year}')

    if len(map_source_year) != 4 or not is_int(census_year):
        raise ValueError(f'Invalid maps source year {map_source_year}')

    glob_paths = [ glob(item) for item in args.distance_files ]
    distance_file_paths: List[str] = [ item for sublist in glob_paths for item in sublist ]

    num_files = len(distance_file_paths)

    print('------------------------------------------')
    print(f'Importing {num_files} file(s)\n')


    results = []

    for i, distance_file_path in enumerate(distance_file_paths):
        success = True
        print(f'Loading [{i+1}/{num_files}] {distance_file_path}')

        state, location_type, location = parse_distance_filename(distance_file_path)

        distance_set = query.create_db_distance_set(state, location_type, location, census_year, map_source_year)

        print(f'Importing distances from {distance_set}')

        import_distances_result = import_distances(
            state=state,
            location_type=location_type,
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
    To import all model data distance file named Contained_in_Madison_City_of_WI_driving_distances.csv:

        python ./db_import_distances_cli.py ../datasets/driving/Contained_in_Madison_City_of_WI/Contained_in_Madison_City_of_WI_driving_distances.csv
        '''
    )
    parser.add_argument('census_year', nargs=1, help='The year of the census data used to generate the distances')
    parser.add_argument('map_source_year', nargs=1, help='The year of the map data used to generate the distances')
    parser.add_argument('distance_files', nargs='+', help='One or distance csv files to import')
    parser.add_argument('-l', '--logdir', default=DEFAULT_LOG_DIR, type=str, help='The directory to error files to ')

    main(parser.parse_args())

