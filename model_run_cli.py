#######################################
#Created on 6 December 2023
#
#@author: Voting Rights Code
#######################################

''' Command line util to run models '''

import argparse
import datetime
from glob import glob
from multiprocessing import Pool
import os
import sys
from typing import List

from tqdm import tqdm

from model_config import PollingModelConfig
import model_run
import utils

DEFAULT_MULTI_PROCESS_CONCURRENT = 1

def load_configs(config_paths: List[str], logdir: str) -> tuple[bool, List[PollingModelConfig]]:
    ''' Look through the list of files and confim they exist on disk, print any missing files or errors. '''
    valid = True
    results: List[PollingModelConfig] = []

    log_date_prefix = datetime.datetime.now().strftime('%Y%m%d%H%M%S')

    for config_path in config_paths:
        if not os.path.isfile(config_path):
            print(f'Invalid path {config_path}')
            valid = False
        else:
            try:
                config = PollingModelConfig.load_config(config_path)
                if logdir:
                    config_file_basename = os.path.basename(config.config_file_path)
                    log_file_name = f'{log_date_prefix}_{config_file_basename}.log'
                    config.log_file_path = os.path.join(
                       logdir,
                       log_file_name,
                    )
                results.append(config)

            # pylint: disable-next=broad-exception-caught
            except Exception as exception:
                print(f'Failed to parse {config_path} due to:\n{exception}')
                valid = False

    return (valid, results)

def run_config(config: PollingModelConfig, log: bool=False, outtype: str='db', verbose=False):
    ''' run a config file '''

    if verbose and outtype == model_run.OUT_TYPE_DB:
        # pylint: disable-next=line-too-long
        print(f'Starting config: {config.config_file_path} -> BigQuery {outtype} output with config set {config.config_set} and name {config.config_name}')
    elif verbose and outtype == model_run.OUT_TYPE_CSV:
        print(f'Starting config: {config.config_file_path} -> CSV output to directory {config.result_folder}')

    model_run.run_on_config(config, log, outtype)
    if verbose:
        print(f'Finished config: {config.config_file_path}')


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

    # Handle wildcards in Windows properly
    glob_paths = [ glob(item) for item in args.configs ]
    config_paths: List[str] = [ item for sublist in glob_paths for item in sublist ]

    # Check that all files are valid, exist if they do not exist
    valid, configs = load_configs(config_paths, logdir)
    if not valid:
        sys.exit(1)

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
    To run all configs in a given folder, parallel processing 4 at a time, and write log files out to the logs
    directory:

        python ./model_run_cli.py -c4 -l logs ./Gwinnett_County_GA_no_bg_school_fire_configs/*.yaml

    To run all configs run one at a time, extra logging printed to the console,
    and write log files out to the logs directory:

        python ./model_run_cli.py -vv -l logs ./Gwinnett_County_GA_no_bg_school_fire_configs/*.yaml

    To run only the Gwinnett_config_no_bg_11 config and write log files out to the logs directory:

        python ./model_run_cli.py -l logs ./Gwinnett_County_GA_no_bg_school_fire_configs/Gwinnett_config_no_bg_11.yaml
        '''
    )
    parser.add_argument('configs', nargs='+', help='One or more yaml configuration files to run.')
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
