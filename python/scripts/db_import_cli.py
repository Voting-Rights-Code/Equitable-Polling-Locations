'''
A command line utility to read in legacy (pre-db) CSVs into the database from past model runs.
'''

from typing import List, Tuple

import argparse
from glob import glob
import os
import sys

from python.database import models, imports
from python.database.query import Query
from python.database.imports import print_all_import_results

from python.solver.model_config import PollingModelConfig
from python.utils import (
    build_precinct_summary_file_path, build_residence_summary_file_path,
    build_results_file_path, build_y_ede_summary_file_path, current_time_utc,
)
from python.utils.environments import load_env
from python.utils.directory_constants import RESULTS_BASE_DIR

MODEL_RUN_ID = 'model_run_id'

RESULTS_PATH = 'results_path'
PRECINCT_DISTANCES_PATH = 'precinct_distances_path'
RESIDENCE_DISTANCES_PATH = 'residence_distances_path'
EDE_PATH = 'EDE_PATH'

DEFAULT_LOG_DIR='logs'
IMPORT_ERROR_LOG_FILE='import_errors.csv'

def output_file_paths(config: PollingModelConfig) -> dict[str, str]:
    ''' Resturns a dictionary of paths to where the results file for a given ModelConfig instance can be found. '''

    config_name = config.config_name
    result_folder = os.path.join(RESULTS_BASE_DIR, config.config_set)

    if not os.path.exists(result_folder):
        raise FileNotFoundError(f'File {result_folder} not found')

    result_file = build_results_file_path(result_folder, config_name)
    precinct_summary_file = build_precinct_summary_file_path(result_folder, config_name)
    residence_summary_file = build_residence_summary_file_path(result_folder, config_name)
    y_ede_summary_file = build_y_ede_summary_file_path(result_folder, config_name)

    results = {
        RESULTS_PATH: result_file,
        PRECINCT_DISTANCES_PATH: precinct_summary_file,
        RESIDENCE_DISTANCES_PATH: residence_summary_file,
        EDE_PATH: y_ede_summary_file,
    }

    return results

def import_model_config(
        query: Query,
        path: str,
        config_set_override: str=None,
        config_name_override: str=None,
) -> Tuple[models.ModelConfig, dict[str, str]]:
    '''
    Imports a model config into the database.  If this model config already exists then a duplicate will not be created.

    Returns:
        A tuple containing a PollingModelConfig and a dictionary of expected result file paths

    '''
    config_source = PollingModelConfig.load_config(path)
    print('config source', config_source)

    paths = output_file_paths(config_source)

    db_model_config = query.create_db_model_config(config_source, config_set_override, config_name_override)

    return (db_model_config, paths)


def main(args: argparse.Namespace):
    ''' Main entrypoint '''

    logdir = args.logdir
    environment = load_env(args.environment)


    glob_paths = [ glob(item) for item in args.configs ]
    config_paths: List[str] = [ item for sublist in glob_paths for item in sublist ]

    num_files = len(config_paths)

    print('------------------------------------------')
    print(f'Importing {num_files} file(s) into {environment}\n')


    results = []

    for i, config_path in enumerate(config_paths):
        query = Query(environment)

        success = True
        print(f'Loading [{i+1}/{num_files}] {config_path}')

        (model_config, file_paths) = import_model_config(query, config_path)
        config_set = model_config.config_set
        config_name = model_config.config_name

        model_config = query.find_or_create_model_config(model_config)
        print(f'Importing result files from {model_config}')

        # TODO Fix the hard coding
        model_run = query.create_model_run(model_config.id, 'chad', '', current_time_utc())
        print(f'Created {model_run}')

        # Import each csv file for this run
        edes_import_result = imports.import_edes(
            environment,
            config_set, config_name, model_run.id, csv_path=file_paths[EDE_PATH], log=True,
        )
        results_import_result = imports.import_results(
            environment,
            config_set, config_name, model_run.id, csv_path=file_paths[RESULTS_PATH], log=True,
        )
        precinct_distances_import_result = imports.import_precinct_distances(
            environment,
            config_set, config_name, model_run.id, csv_path=file_paths[PRECINCT_DISTANCES_PATH], log=True,
        )
        residence_distances_import_result = imports.import_residence_distances(
            environment,
            config_set, config_name, model_run.id, csv_path=file_paths[RESIDENCE_DISTANCES_PATH], log=True,
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
            results.append(current_run_result)

        model_run.success = success

        print('\n\n')

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
        # pylint: disable-next=line-too-long
        description='A command line utility to read in legacy (pre-db) CSVs into the bigquery database from past model runs.',
        epilog='''
Examples:
    To import all model data from the config set named Chesterfield_County_VA_potential_configs:

        python -m python.scripts.db_import_cli ./Chesterfield_County_VA_potential_configs/*yaml
        '''
    )
    parser.add_argument('configs', nargs='+', help='One or more yaml configuration files to run.')
    parser.add_argument('-e', '--environment', type=str, help='The environment to use')
    parser.add_argument('-l', '--logdir', default=DEFAULT_LOG_DIR, type=str, help='The directory to erros files to ')

    main(parser.parse_args())
