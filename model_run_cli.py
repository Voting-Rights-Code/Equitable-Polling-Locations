''' Command line util to run models '''

import argparse
import datetime
from multiprocessing import Pool
import os
import sys
from typing import List

from tqdm import tqdm

from polling_model_config import PollingModelConfig
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

def run_config(config: PollingModelConfig, log: bool=False, verbose=False):
    ''' run a config file '''

    # pylint: disable-next=line-too-long
    if verbose:
        print(f'Starting config: {config.config_file_path} -> Output dir: {config.result_folder}')
    model_run.run_on_config(config, log)
    if verbose:
        print(f'Finished config: {config.config_file_path}')


def main(args: argparse.Namespace):
    ''' Main entrypoint '''

    logdir = args.logdir
    if logdir:
        if not os.path.exists(logdir):
            print(f'Invalid log dir: {logdir}')
            sys.exit(1)
        else:
            print(f'Writing logs to dir: {logdir}')

    # Check that all files are valid, exist if they do not exist
    valid, configs = load_configs(args.configs, logdir)
    if not valid:
        sys.exit(1)

    total_files: int = len(configs)

    # If any level of verbosity is set, the display SCIP logs
    log: bool = args.verbose > 0

    if args.concurrent > 1:
        print(f'Running concurrent with a pool size of {args.concurrent} against {total_files} config file(s)')
        with Pool(args.concurrent) as pool:
            for _ in tqdm(pool.imap_unordered(run_config, configs), total=total_files):
                pass
    else:
        # Disable function timers messages unless verbosity 2 or higher is set
        if args.verbose > 1:
            utils.set_timers_enabled(True)

        print(f'Running single process against {total_files} config file(s)')

        for config_file in configs:
            run_config(config_file, log, True)
            print('--------------------------------------------------------------------------------')

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('configs', nargs='+')
    parser.add_argument('-c', '--concurrent', default=DEFAULT_MULTI_PROCESS_CONCURRENT, type=int)
    parser.add_argument('-v', '--verbose', action='count', default=0)
    parser.add_argument('-l', '--logdir', type=str)

    main(parser.parse_args())
