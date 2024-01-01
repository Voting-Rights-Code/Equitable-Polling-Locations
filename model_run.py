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

from model_data import (build_source, clean_data, alpha_min)
from model_factory import polling_model_factory
from model_solver import solve_model
from model_results import (
    incorporate_result,
    demographic_domain_summary,
    demographic_summary,
    write_results,
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

    # 1. compute optimal solution without excluding penalized sites (model 1)
    # 2. if there are no penalized sites in the optimal solution,
    #    continue to result_df with solution to model 1 (this includes the case
    #    that there are no penalized sites)
    # 3. convert objective value to KP score (kp1)
    # 4. compute optimal solution excluding penalized sites (model 2)
    # 5. convert objective value to KP score (kp2)
    # 6. compute penalty as (kp2-kp1)/len(selected penalized sites in model 1)
    # 7. compute optimal soltuion including penalized sites, but with given penalty (model 3)
    # 8. continue to result_df with solution to model 3

    #build model
    ea_model = polling_model_factory(dist_df, alpha, config, exclude_penalized_sites=False)
    if log:
        print(f'model built for {run_prefix}.')

    #solve model
    solve_model(ea_model, config.time_limit, log=log, log_file_path=config.log_file_path)
    if log:
        print(f'model solved for {run_prefix}.')

    #incorporate result into main dataframe
    result_df = incorporate_result(dist_df, ea_model)

    selected_sites = set(result_df.id_dest)
    penalized_selections = {x for x in selected_sites if x in config.penalized_sites}

    penalized_string = "\n  ".join(sorted(penalized_selections))
    print(f'Unpenalized model selected {len(penalized_selections)} penalized sites:\n  {penalized_string}')

    if penalized_selections: # penalized sites were selected, move to step 3
        obj_value = pyo.value(ea_model.obj)
        kp1 = -1/(config.beta*alpha)*math.log(obj_value) if config.beta else obj_value
            

        # solve model with penalized sites excluded
        ea_model_exclusions = polling_model_factory(dist_df, alpha, config, exclude_penalized_sites=True)
        if log:
            print(f'model with exclusions built for {run_prefix}.')

        #solve model
        solve_model(ea_model_exclusions, config.time_limit, log=log, log_file_path=config.log_file_path)
        if log:
            print(f'model with exclusions solved for {run_prefix}.')
        
        obj_value = pyo.value(ea_model_exclusions.obj)
        kp2 = -1/(config.beta*alpha)*math.log(obj_value) if config.beta else obj_value

        penalty = (kp2-kp1)/len(penalized_selections)

        print(f'{kp1 = :.2f}, {kp2 = :.2f}')
        print(f'computed penalty is {penalty:.2f}')

        ea_model_penalized =  polling_model_factory(dist_df, alpha, config,
                                                    exclude_penalized_sites=False,
                                                    site_penalty=penalty,
                                                    kp_penalty_parameter=kp1)
        if log:
            print(f'penalized model built for {run_prefix}.')

        #solve model
        solve_model(ea_model_penalized, config.time_limit, log=log, log_file_path=config.log_file_path)
        if log:
            print(f'penalized model solved for {run_prefix}.')

        #incorporate result into main dataframe
        result_df = incorporate_result(dist_df, ea_model_penalized)
        
        selected_sites = set(result_df.id_dest)
        penalized_selections = {x for x in selected_sites if x in config.penalized_sites}

        if penalized_selections:
            penalized_string = "\n  ".join(sorted(penalized_selections))
            print(f'Penalized model selected {len(penalized_selections)} penalized sites:\n  {penalized_string}')
        else:
            print('Penalized model selected no penalized sites.')

        
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
