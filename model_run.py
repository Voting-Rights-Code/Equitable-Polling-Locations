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
from model_solver import solve_model
from model_results import (
    incorporate_result,
    demographic_domain_summary,
    demographic_summary,
    write_results,
    compute_kp_score
)

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

def incorporate_penalties(dist_df, alpha, run_prefix, result_df, ea_model, config: PollingModelConfig, log: bool=False):


    # 0. if there are not penalized sites, we're done
    if not config.penalized_sites:
        return result_df
    
    # 1. if none of the penalized sites were selected by model 1 (no penalties), we're done
    selected_sites = set(result_df.id_dest)
    penalized_selections = {x for x in selected_sites if x in config.penalized_sites}
    if not penalized_selections:
        print('No penalized sites selected')
        return result_df
    
    # otherwise, start a log and continue the algorithm
    penalty_log = open(get_log_path(config,'penalty'), 'a')
    penalty_log.write('Model 1: original model with no penalties\n')
    penalty_log.write(f'Selected {len(penalized_selections)} penalized sites:\n')
    for s in sorted(penalized_selections):
        penalty_log.write(f'\t ---> {s}\n')

    # 2. convert objective value to KP score (kp1)
    obj_value = pyo.value(ea_model.obj)
    kp1 = -1/(config.beta*alpha)*math.log(obj_value) if config.beta else obj_value   
    penalty_log.write(f'KP Objective = {kp1:.2f}\n')

    # 3. compute optimal solution excluding penalized sites (model 2)
    ea_model_exclusions = polling_model_factory(dist_df, alpha, config, exclude_penalized_sites=True)
    if log:
        print(f'Model 2 (excludes penalized sites) built for {run_prefix}')

    solve_model(ea_model_exclusions, config.time_limit, log=log, log_file_path=get_log_path(config,'model2'))
    if log:
        print(f'Model 2 solved for {run_prefix}.')

    # 4. convert objective value to KP score (kp2)
    obj_value = pyo.value(ea_model_exclusions.obj)
    kp2 = -1/(config.beta*alpha)*math.log(obj_value) if config.beta else obj_value
    
    # 5. compute penalty as (kp2-kp1)/len(selected penalized sites in model 1)
    penalty = (kp2-kp1)/len(penalized_selections)
    if log:
        print(f'{kp1 = :.2f}, {kp2 = :.2f}')
        print(f'computed penalty is {penalty:.2f}')
    penalty_log.write('\nModel 2: penalized sites excluded\n')
    penalty_log.write(f'KP Objective = {kp2:.2f}\n')
     
    # 6. compute optimal solution including penalized sites applying calculate penalty (model 3)
    ea_model_penalized =  polling_model_factory(dist_df, alpha, config,
                                            exclude_penalized_sites=False,
                                            site_penalty=penalty,
                                            kp_penalty_parameter=kp1)
    if log:
        # final_model = ('penalized', ea_model_penalized)
        print(f'Model 3 (penalized model) built for {run_prefix}.')

    solve_model(ea_model_penalized, config.time_limit, log=log, log_file_path=get_log_path(config,'model3'))
    if log:
        print(f'Model 3 solved for {run_prefix}.')

    # 8. continue to result_df with solution to model 3
    result_df = incorporate_result(dist_df, ea_model_penalized)
    

    selected_sites = set(result_df.id_dest)
    penalized_selections = {x for x in selected_sites if x in config.penalized_sites}
    penalty_log.write('\nModel 3: penalized model\n')
    penalty_log.write(f'Penalty applied to each site = {penalty:.2f}\n')
    if penalized_selections:
        penalty_log.write(f'Selected {len(penalized_selections)} penalized sites:\n')
        for s in sorted(penalized_selections):
            penalty_log.write(f'\t ---> {s}\n')
    else:
        penalty_log.write('Selected no penalized sites.\n')

    # report some final statistics
    obj_value = pyo.value(ea_model_penalized.obj)
    kp_pen = -1/(config.beta*alpha)*math.log(obj_value) if config.beta else obj_value
    kp = compute_kp_score(result_df, config.beta, alpha=alpha)
    penalty_log.write(f'Penalized KP Optimal = {kp_pen:.2f}\n')
    penalty_log.write(f'KP Optimal = {kp:.2f}\n')
    penalty_log.write(f'Penalty = {kp_pen-kp:.2f}\n')


    return result_df

def get_log_path(config: PollingModelConfig, specifier: str):
    base_path = '.'.join(config.log_file_path.split('.')[0:-1])
    return f'{base_path}.{specifier}.log'
