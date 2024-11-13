'''
A command line utility to read in legacy (pre-db) CSVs into the database from past model runs.
'''

from typing import List, Tuple

import argparse
from glob import glob
import os
import sys


import pandas as pd

import models as Models
import db

from model_config import PollingModelConfig
from utils import current_time_utc

MODEL_RUN_ID = 'model_run_id'

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASETS_DIR = os.path.join(CURRENT_DIR, 'datasets')

RESULTS_PATH = 'results_path'
PRECINCT_DISTANCES_PATH = 'precinct_distances_path'
RESIDENCE_DISTANCES_PATH = 'residence_distances_path'
EDE_PATH = 'EDE_PATH'

DEFAULT_LOG_DIR='logs'
IMPORT_ERROR_LOG_FILE='import_errors.csv'

def output_file_paths(config: PollingModelConfig) -> dict[str, str]:
    ''' Resturns a dictionary of paths to where the results file for a given ModelConfig instance can be found. '''
    config_file_basename = f'{os.path.basename(config.config_file_path)}'.replace('.yaml','')
    run_prefix = f'{os.path.dirname(config.config_file_path)}.{config_file_basename}'

    result_folder = config.result_folder

    source_file_name = config.location + '.csv'
    source_path = os.path.join(DATASETS_DIR, 'polling', config.location, source_file_name)
    if not os.path.exists(source_path):
        raise FileNotFoundError(f'File {source_path} not found')


    if not os.path.exists(result_folder):
        raise FileNotFoundError(f'Results folder {result_folder} not found.')

    result_file = f'{run_prefix}_result.csv'
    precinct_summary = f'{run_prefix}_precinct_distances.csv'
    residence_summary = f'{run_prefix}_residence_distances.csv'
    y_ede_summary = f'{run_prefix}_edes.csv'

    results = {
        RESULTS_PATH: os.path.join(result_folder, result_file),
        PRECINCT_DISTANCES_PATH: os.path.join(result_folder, precinct_summary),
        RESIDENCE_DISTANCES_PATH: os.path.join(result_folder, residence_summary),
        EDE_PATH: os.path.join(result_folder, y_ede_summary),
    }

    return results

def import_model_config(config_set: str, config_name: str, path: str) -> Tuple[Models.ModelConfig, dict[str, str]]:
    '''
    Imports a model config into the database.  If this model config already exists then a duplicate will not be created.

    Returns:
        A tuple containing a PollingModelConfig and a dictionary of expected result file paths

    '''
    config_source = PollingModelConfig.load_config(path)

    paths = output_file_paths(config_source)

    config_data = {
        'config_set': config_set,
        'config_name': config_name,
    }

    for column in Models.ModelConfig.__table__.columns:
        column_name = column.name
        if column_name in ['id', 'created_at']:
            continue

        value = getattr(config_source, column_name)
        # print(f'{column_name} -> {value}')

        config_data[column_name] = value

    result = Models.ModelConfig(**config_data)

    result.id = result.generate_id()

    return (result, paths)



def import_edes_csv(config_set: str, config_name: str, model_run_id: str, csv_path: str) -> db.ImportResult:
    ''' Imports an existing EDEs csv into the database for a given mode_run_id. '''

    column_renames = {}
    ignore_columns = []
    add_columns = { 'model_run_id': model_run_id }

    return db.csv_to_bigquery(
        config_set=config_set,
        config_name=config_name,
        model_class=Models.EDES,
        csv_path=csv_path,
        ignore_columns=ignore_columns,
        column_renames=column_renames,
        add_columns=add_columns
    )

def import_precinct_distances_csv(
        config_set: str,
        config_name: str,
        model_run_id: str,
        csv_path: str
) -> db.ImportResult:
    ''' Imports an existing precinct distances csv into the database for a given mode_run_id. '''

    column_renames = {}
    ignore_columns = []
    add_columns = { 'model_run_id': model_run_id }

    return db.csv_to_bigquery(
        config_set=config_set,
        config_name=config_name,
        model_class=Models.PrecintDistance,
        csv_path=csv_path,
        ignore_columns=ignore_columns,
        column_renames=column_renames,
        add_columns=add_columns
    )

def import_residence_distances_csv(
        config_set: str,
        config_name: str,
        model_run_id: str,
        csv_path: str
) -> db.ImportResult:
    ''' Imports an existing residence distances csv into the database for a given mode_run_id. '''

    column_renames = {}
    ignore_columns = []
    add_columns = { 'model_run_id': model_run_id }

    return db.csv_to_bigquery(
        config_set=config_set,
        config_name=config_name,
        model_class=Models.ResidenceDistance,
        csv_path=csv_path,
        ignore_columns=ignore_columns,
        column_renames=column_renames,
        add_columns=add_columns
    )

def import_results_csv(config_set: str, config_name: str, model_run_id: str, csv_path: str) -> db.ImportResult:
    ''' Imports an existing precinct distances csv into the database for a given mode_run_id. '''

    column_renames = {
        'non-hispanic': 'non_hispanic',
        'Weighted_dist': 'weighted_dist',
        'KP_factor': 'kp_factor',
    }
    ignore_columns = ['V1']
    add_columns = { 'model_run_id': model_run_id }

    return db.csv_to_bigquery(
        config_set=config_set,
        config_name=config_name,
        model_class=Models.Result,
        csv_path=csv_path,
        ignore_columns=ignore_columns,
        column_renames=column_renames,
        add_columns=add_columns
    )


def print_all_import_results(import_results: List[db.ImportResult], output_path: str=None):
    ''' Prints to the screen a summary of all import results. '''

    data = {
        'timestamp': [ r.timestamp for r in import_results ],
        'config_set': [ r.config_set for r in import_results ],
        'config_name': [ r.config_name for r in import_results ],
        'success': [ r.success for  r in import_results ],
        'table_name': [ r.table_name for r in import_results ],
        'source_file': [ r.source_file for r in import_results ],
        'rows_written': [ r.rows_written for  r in import_results ],
        'error': [ str(r.exception or '') for  r in import_results ],
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


def main(args: argparse.Namespace):
    ''' Main entrypoint '''

    config_set = args.config_set_name[0]
    logdir = args.logdir

    glob_paths = [ glob(item) for item in args.configs ]
    config_paths: List[str] = [ item for sublist in glob_paths for item in sublist ]

    num_files = len(config_paths)

    print(f'Importing {num_files} file(s)\n')


    results = []

    for i, config_path in enumerate(config_paths):
        success = True
        print(f'Loading [{i+1}/{num_files}] {config_path}')
        config_file_basename = os.path.basename(config_path)
        config_name = config_file_basename.replace('.yaml','')

        (model_config, file_paths) = import_model_config(config_set, config_name, config_path)

        model_config = db.find_or_create_model_config(model_config)
        print(f'Importing result files from {model_config}')

        # TODO Fix the hard coding
        model_run = db.create_model_run(model_config.id, 'chad', '', current_time_utc())
        print(f'Created {model_run}')

        # Import each csv file for this run
        edes_import_result = import_edes_csv(
            config_set, config_name, model_run.id, file_paths[EDE_PATH]
        )
        results_import_result = import_results_csv(
            config_set, config_name, model_run.id, file_paths[RESULTS_PATH]
        )
        precinct_distances_import_result = import_precinct_distances_csv(
            config_set, config_name, model_run.id, file_paths[PRECINCT_DISTANCES_PATH]
        )
        residence_distances_import_result = import_residence_distances_csv(
            config_set, config_name, model_run.id, file_paths[RESIDENCE_DISTANCES_PATH]
        )

        current_run_results = [
            edes_import_result,
            results_import_result,
            precinct_distances_import_result,
            residence_distances_import_result,
        ]

        # check for any problems and add the current_run_results to the overall results
        for current_run_result in current_run_results:
            success = success and current_run_result.success
            results.append(edes_import_result)

        model_run.success = success

        print('\n\n')

        db.commit()


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
        description='A command line utility to read in legacy (pre-db) CSVs into the bigquery database from past model runs.',
        epilog='''
Examples:
    To import all model data from the config set named Chesterfield_County_VA_potential_configs:

        python ./db_import_cli.py Chesterfield_County_VA_potential_configs ./Chesterfield_County_VA_potential_configs/*yaml
        '''
    )
    parser.add_argument('config_set_name', nargs=1, help='the config set name')
    parser.add_argument('configs', nargs='+', help='One or more yaml configuration files to run.')
    parser.add_argument('-l', '--logdir', default=DEFAULT_LOG_DIR, type=str, help='The directory to erros files to ')


    main(parser.parse_args())
