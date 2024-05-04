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
import math
import sys
import warnings
import pyomo.environ as pyo

from model_config import PollingModelConfig
from time import time

from model_data import (build_source, clean_data, alpha_min)
from model_factory import polling_model_factory
from model_solver import solve_model, incorporate_penalties
from model_results import (
    incorporate_result,
    demographic_domain_summary,
    demographic_summary,
    write_results
)

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
DATASETS_DIR = os.path.join(CURRENT_DIR, 'datasets')

def run_on_config(config: PollingModelConfig, log: bool=False):
    '''
    The entry point to exectue a pyomo/scip run.
    '''

    config_file_basename = f'{os.path.basename(config.config_file_path)}'.replace('.yaml','')
    run_prefix = f'{config.location}_configs.{config_file_basename}'

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

    #if this a run with penalized sites, incorporate site penalties 
    if config.penalized_sites:
        # if some of the the penalized sites were selected by model 1 (no penalties), run penalty algorithm
        selected_sites = set(result_df.id_dest)
        penalized_selections = {x for x in selected_sites if x in config.penalized_sites}
        if  penalized_selections:
            print('Penalized sites chosen. Running penalized optimizaion')
            ea_model_penalized = incorporate_penalties(dist_df, alpha, run_prefix, result_df, ea_model, config, log)
            #incorporate penalized results
            result_df = incorporate_result(dist_df, ea_model_penalized)

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




    
    





