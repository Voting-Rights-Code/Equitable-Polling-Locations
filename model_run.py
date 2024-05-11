#######################################
#Created on 6 December 2023
#
#@author: Voting Rights Code
#######################################
'''
This file sets up a pyomo/scip run based on a config file, e.g.
Gwinnett_GA_configs/Gwinnett_config_full_11.py
'''

import os
import sys
import warnings

from model_config import PollingModelConfig

from model_data import (build_source, clean_data, alpha_min)
from model_factory import polling_model_factory
from model_solver import solve_model
from model_results import (
    incorporate_result,
    demographic_domain_summary,
    demographic_summary,
    write_results,
)
from model_penalties import incorporate_penalties

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASETS_DIR = os.path.join(CURRENT_DIR, 'datasets')

def run_on_config(config: PollingModelConfig, log: bool=False):
    '''
    The entry point to exectue a pyomo/scip run.
    '''

    config_file_basename = f'{os.path.basename(config.config_file_path)}'.replace('.yaml','')
    run_prefix = f'{os.path.dirname(config.config_file_path)}.{config_file_basename}'

    #check if source data avaible
    source_file_name = config.location + '.csv'
    source_path = os.path.join(DATASETS_DIR, 'polling', config.location, source_file_name)
    if not os.path.exists(source_path):
        warnings.warn(f'File {source_path} not found. Creating it.')
        build_source(config.location)

    #get main data frame
    dist_df = clean_data(config, False)

    #get alpha 
    alpha_df = clean_data(config, True)
    alpha  = alpha_min(alpha_df)

    #build model
    ea_model = polling_model_factory(dist_df, alpha, config)
    if log:
        print(f'model built for {run_prefix}.')

    #solve model
    solve_model(ea_model, config.time_limit, log=log, log_file_path=config.log_file_path)
    if log:
        print(f'model solved for {run_prefix}.')

    #incorporate result into main dataframe
    result_df = incorporate_result(dist_df, ea_model)

    #incorporate site penalties as appropriate
    result_df = incorporate_penalties(dist_df, alpha, run_prefix, result_df, ea_model, config, log)

    #calculate the new alpha given this assignment
    alpha_new = alpha_min(result_df)

    #calculate the average distances traveled by each demographic to the assigned precinct
    demographic_prec = demographic_domain_summary(result_df, 'id_dest')

    #calculate the average distances traveled by each demographic by residence
    demographic_res = demographic_domain_summary(result_df, 'id_orig')

    #calculate the average distances (and y_ede if beta !=0) traveled by each demographic
    demographic_ede = demographic_summary(demographic_res, result_df, config.beta, alpha_new)

    result_folder = config.result_folder

    write_results(
        result_folder,
        run_prefix,
        result_df,
        demographic_prec,
        demographic_res,
        demographic_ede,
    )

    return result_folder




