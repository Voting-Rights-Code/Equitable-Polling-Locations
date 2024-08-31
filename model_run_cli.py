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

def load_configs(config_paths: List[str], logdir: str) -> (bool, List[PollingModelConfig]):
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

def run_config(config: PollingModelConfig, log: bool=False, replace: bool=False, outtype: str = 'prod', verbose=False):
    ''' run a config file '''

    # pylint: disable-next=line-too-long
    if verbose & outtype in ['prod']:
        print(f'Starting config: {config.config_file_path} -> BigQuery {outtype} output with config set {config.config_set} and name {config.config_name}')
    elif verbose & outtype == 'csv':
        print(f'Starting config: {config.config_file_path} -> CSV output to directory {config.result_folder}')

    model_run.run_on_config(config, log, replace, outtype)
    if verbose:
        print(f'Finished config: {config.config_file_path}')


def main(args: argparse.Namespace):
    ''' Main entrypoint '''

    logdir = args.logdir
    replace = args.replace
    outtype = args.outtype
    if logdir:
        if not os.path.exists(logdir):
            print(f'Invalid log dir: {logdir}')
            sys.exit(1)
        else:
            print(f'Writing logs to dir: {logdir}')

    if outtype not in ['csv', 'prod']:
        print(f'Invalid outtype: {outtype}')
        sys.exit(1)

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
            for _ in tqdm(pool.imap_unordered(lambda x: run_config(x, replace, outtype), configs), total=total_files):
                pass
    else:
        # Disable function timers messages unless verbosity 2 or higher is set
        if args.verbose > 1:
            utils.set_timers_enabled(True)

        print(f'Running single process against {total_files} config file(s)')

        for config_file in configs:
            run_config(config_file, log, outtype, replace, True)
            print('--------------------------------------------------------------------------------')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='A commandline tool that chooses an optimal set of polling locations from a set of potential locations.',
        epilog='''
Examples:
    To run all expanded configs, parallel processing 4 at a time, and write log files out to the logs
    directory:

        python ./model_run_cli.py -c4 -l logs ./Gwinnett_GA_configs/Gwinnett_config_expanded_*.yaml

    To run all full configs run one at a time, extra logging printed to the console,
    and write log files out to the logs directory:

        python ./model_run_cli.py -vv -l logs ./Gwinnett_GA_configs/Gwinnett_config_full_*.yaml

    To run only the full_11 and write log files out to the logs directory:

        python ./model_run_cli.py -l logs ./Gwinnett_GA_configs/Gwinnett_config_full_11.yaml
        '''
    )
    parser.add_argument('configs', nargs='+', help='One or more yaml configuration files to run.')
    parser.add_argument('-c', '--concurrent', default=DEFAULT_MULTI_PROCESS_CONCURRENT, type=int,
                        help='How many concurrent optimization processes to run at the same time.  ' +
                        'Be mindful of ram availability - full runs can use in excess of 40 GB' +
                        ' for each concurrent process.')
    parser.add_argument('-v', '--verbose', action='count', default=0, help='Print extra logging.')
    parser.add_argument('-l', '--logdir', type=str, help='The directory to output log files to')
    parser.add_argument('-r', '--replace', action='store_true', help = 'Replace existing output data for a given config name and set')
    parser.add_argument('-o', '--outtype', type=str, default = 'prod', help = 'Output location, one of "prod" (production database) or "csv" (local CSV)')

    main(parser.parse_args())
