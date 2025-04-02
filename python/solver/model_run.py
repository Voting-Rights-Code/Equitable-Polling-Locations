#######################################
#Created on 6 December 2023
#
#@author: Voting Rights Code
#######################################
'''
This file sets up a pyomo/scip run based on a config file, e.g.
Gwinnett_County_GA_configs/Gwinnett_config_full_11.py
'''

import os
import warnings

from python.utils import build_locations_distance_file_path
from python.utils.constants import RESULTS_BASE_DIR

from .model_config import PollingModelConfig
from .model_data import (
    build_source,
    clean_data,
    alpha_min,
)
from .model_factory import polling_model_factory
from .model_penalties import incorporate_penalties
from .model_results import (
    incorporate_result,
    demographic_domain_summary,
    demographic_summary,
    write_results_csv,
    write_results_bigquery,
)
from .model_solver import solve_model

OUT_TYPE_DB = 'db'
OUT_TYPE_CSV = 'csv'

def run_on_config(config: PollingModelConfig, log: bool=False, outtype: str = OUT_TYPE_DB):
    '''
    The entry point to exectute a pyomo/scip run.
    '''

    run_prefix = f'{config.config_set}/{config.config_name}'

    source_path = build_locations_distance_file_path(config.location, config.driving, config.log_distance)
    if not os.path.exists(source_path):
        warnings.warn(f'File {source_path} not found. Creating it.')
        build_source(config.location, config.driving, config.log_distance, log)


    #get main data frame
    dist_df = clean_data(config, False, log)

    #get alpha
    alpha_df = clean_data(config, True, log)
    alpha  = alpha_min(alpha_df)

    #build model
    ea_model = polling_model_factory(dist_df, alpha, config)
    if log:
        print(f'model built for {run_prefix}.')

    #solve model
    solve_model(ea_model, config.time_limit, log=log, log_file_path=config.log_file_path)

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

    if outtype == OUT_TYPE_DB:
        write_results_bigquery(
             config,
             result_df,
             demographic_prec,
             demographic_res,
             demographic_ede,
             log=log,
        )
    elif outtype == OUT_TYPE_CSV:
        result_folder = os.path.join(RESULTS_BASE_DIR, config.config_set)

        write_results_csv(
            result_folder,
            config.config_name,
            result_df,
            demographic_prec,
            demographic_res,
            demographic_ede,
         )
    else:
        raise ValueError(f'Unknown out type {outtype}')
