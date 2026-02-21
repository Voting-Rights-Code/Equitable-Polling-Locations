'''
A command line utility to read in legacy (pre-db) CSVs into the database from past model runs.
'''

from typing import List

import argparse
from glob import glob

from python.database.query import Query

from python.solver.model_config import PollingModelConfig
from python.utils.environments import load_env


def main(args: argparse.Namespace):
    ''' Main entrypoint '''

    environment = load_env(args.environment)


    glob_paths = [ glob(item) for item in args.configs ]
    config_paths: List[str] = [ item for sublist in glob_paths for item in sublist ]

    num_files = len(config_paths)

    print('------------------------------------------')
    print(f'Importing {num_files} file(s) into {environment}\n')



    for i, config_path in enumerate(config_paths):
        query = Query(environment)

        print(f'Loading [{i+1}/{num_files}] {config_path}')

        model_config = PollingModelConfig.load_config(config_path)
        config_set = model_config.config_set
        config_name = model_config.config_name
        db_model_config = query.create_db_model_config(model_config)

        print(f'  Importing: {config_set}/{config_name}')

        model_config = query.find_or_create_model_config(db_model_config)

        print('\n\n')

        query.commit()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        # pylint: disable-next=line-too-long
        description='A command line utility to read configs into the bigquery database.',
        epilog='''
Examples:
    To import all Chesterfield_County_VA_potential_configs configs:

        python -m python.scripts.db_import_config_cli ./datasets/configs/Chesterfield_County_VA_potential_configs/*yaml
        '''
    )
    parser.add_argument('configs', nargs='+', help='One or more yaml configuration files to run.')
    parser.add_argument('-e', '--environment', type=str, help='The environment to use')

    main(parser.parse_args())
