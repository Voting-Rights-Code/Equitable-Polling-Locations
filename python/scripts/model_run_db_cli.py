#######################################
#Created on 6 December 2023
#
#@author: Voting Rights Code
#######################################

'''
Command line util to run models from the db.  This differs from model_run_cli.py in that all config
files will be read from the db instead of from yaml files on disk, and all results will be written to
the db.
'''

import argparse
import datetime
from multiprocessing import Pool
import os
import sys
from typing import List

from tqdm import tqdm

import python.database as db
from python.solver.model_config import PollingModelConfig
from python.solver import model_run
from python.database.models.model_config import ModelConfig
from python import utils

DEFAULT_MULTI_PROCESS_CONCURRENT = 1

def load_configs(config_args: List[str], logdir: str) -> List[PollingModelConfig]:
    ''' Loads configs from the db '''
    # valid = True
    results: List[PollingModelConfig] = []

    # log_date_prefix = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

    results: List[PollingModelConfig] = []

    log_date_prefix = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

    for config_arg in config_args:
        configs: List[ModelConfig] = None

        config_arg_parts = config_arg.split('/')
        num_config_arg_parts = len(config_arg_parts)

        config_set = config_arg_parts[0]
        if num_config_arg_parts == 1:
            # Find all the latest configs by a config_set
            configs = db.find_model_configs_by_config_set(config_set)
            if not configs:
                print(f'Invalid config: {config_arg}')
                sys.exit(1)
        elif num_config_arg_parts == 2:
            # Find a single config by config_set and config_name that is the latest
            config_name = config_arg_parts[1]

            config = db.find_model_configs_by_config_set_and_config_name(config_set, config_name)
            if config:
                configs = [ config ]
            else:
                print(f'Invalid config: {config_arg}')
                sys.exit(1)
        else:
            print(f'Invalid config: {config_arg}')
            sys.exit(1)

        for config in configs:
            # Convert the db config into a legacy polling model config object
            polling_model_config = db.create_polling_model_config(config)

            if logdir:
                # Setup logs as needed
                # pylint: disable-next=line-too-long
                log_file_name = f'{log_date_prefix}_db_run_{polling_model_config.db_id}_{polling_model_config.config_set}_{polling_model_config.config_name}.log'
                polling_model_config.log_file_path = os.path.join(
                    logdir,
                    log_file_name,
                )

            results.append(polling_model_config)

            print(f'Config: {config.id} {config.config_set}/{config.config_name}')

    return results


def run_config(config: PollingModelConfig, log: bool=False, verbose=False):
    ''' run a config file '''

    config_info = f'{config.db_id} {config.config_set}/{config.config_name}'
    # pylint: disable-next=line-too-long
    print(f'Starting config: {config_info}')

    model_run.run_on_config(config, log, 'db')
    if verbose:
        print(f'Finished config: {config_info}')


def main(args: argparse.Namespace):
    ''' Main entrypoint '''

    logdir = args.logdir
    outtype = args.outtype
    if outtype == model_run.OUT_TYPE_DB:
        #Force the database prompt immediately upon run, if running on DB
        utils.get_env_var_or_prompt('DB_PROJECT', default_value='equitable-polling-locations')
        utils.get_env_var_or_prompt('DB_DATASET')

    if logdir:
        if not os.path.exists(logdir):
            print(f'Invalid log dir: {logdir}')
            sys.exit(1)
        else:
            print(f'Writing logs to dir: {logdir}')


    # Check that all files are valid, exist if they do not exist
    configs = load_configs(args.configs, logdir)

    total_files: int = len(configs)

    # If any level of verbosity is set, the display SCIP logs
    log: bool = args.verbose > 0

    if args.concurrent > 1:
        print(f'Running concurrent with a pool size of {args.concurrent} against {total_files} config file(s)')
        with Pool(args.concurrent) as pool:
            for _ in tqdm(pool.imap_unordered(lambda x: run_config(x, log, outtype), configs), total=total_files):
                pass
    else:
        # Disable function timers messages unless verbosity 2 or higher is set
        if args.verbose > 1:
            utils.set_timers_enabled(True)

        print(f'Running single process against {total_files} config file(s)')

        for config_file in configs:
            run_config(config_file, log, outtype)
            print('--------------------------------------------------------------------------------')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        # pylint: disable-next=line-too-long
        description='A commandline tool that chooses an optimal set of polling locations from a set of potential locations.',
        epilog='''
Examples:
    To run all configs in the db from the config_set York_County_SC_original_configs_log, parallel processing 4 at a time, and write log files out to the logs
    directory:

        python ./model_run_db_cli.py -c4 -l logs York_County_SC_original_configs_log

    To run all configs run one at a time, extra logging printed to the console,
    and write log files out to the logs directory:

        python ./model_run_cli.py -vv -l logs York_County_SC_original_configs_log

    To run only the config York_County_SC_year_2016 under the config set York_County_SC_original_configs_log:

        python ./model_run_cli.py -l logs York_County_SC_original_configs_log/York_County_SC_year_2016
        '''
    )
    parser.add_argument('configs', nargs='+', help='One or more config sets and optionally config names. e.g. York_County_SC_original_configs_log/York_County_SC_year_2016')
    parser.add_argument(
        '-c',
        '--concurrent',
        default=DEFAULT_MULTI_PROCESS_CONCURRENT,
        type=int,
        help='How many concurrent optimization processes to run at the same time.  ' +
            'Be mindful of ram availability - full runs can use in excess of 40 GB' +
            ' for each concurrent process.')
    parser.add_argument('-v', '--verbose', action='count', default=0, help='Print extra logging.')
    parser.add_argument('-l', '--logdir', type=str, help='The directory to output log files to')
    parser.add_argument(
        '-o',
        '--outtype',
        choices=[model_run.OUT_TYPE_DB, model_run.OUT_TYPE_CSV],
        default = model_run.OUT_TYPE_DB,
        # pylint: disable-next=line-too-long
        help = f'Output location, one of "{model_run.OUT_TYPE_DB}" (database) or "{model_run.OUT_TYPE_CSV}" (local CSV)',
    )


    main(parser.parse_args())
