import pyomo.environ as pyo
import math

from .model_config import PollingModelConfig

from .model_factory import polling_model_factory
from .model_results import (
    incorporate_result,
    compute_kp_score,
)
from .model_solver import solve_model


def get_log_path(config: PollingModelConfig, specifier: str):
    base_path = '.'.join(config.log_file_path.split('.')[0:-1])
    return f'{base_path}.{specifier}.log'


def compute_kp(config: PollingModelConfig, alpha: float, obj_value: float) -> float:
    if config.beta:
        return -1/(config.beta*alpha)*math.log(obj_value)

    return obj_value


def incorporate_penalties(dist_df, alpha, run_prefix, result_df, ea_model, config: PollingModelConfig, log: bool=False):


    # 0. if there are not penalized sites, we're done
    if not config.penalized_sites:
        return result_df

    # 1. if none of the penalized sites were selected by model 1 (no penalties), we're done
    selected_sites = set(result_df.id_dest)
    penalized_sites = set(dist_df.loc[dist_df['location_type'].isin(config.penalized_sites), 'id_dest'].unique())
    penalized_selections = selected_sites.intersection(penalized_sites)
    if not penalized_selections:
        print('No penalized sites selected')
        return result_df

    # otherwise, start a log and continue the algorithm
    penalty_log = open(get_log_path(config,'penalty'), 'a', encoding='utf-8')
    penalty_log.write('Model 1: original model with no penalties\n')
    penalty_log.write(f'Selected {len(penalized_selections)} penalized sites:\n')
    for s in sorted(penalized_selections):
        penalty_log.write(f'\t ---> {s}\n')

    # 2. convert objective value to KP score (kp1)
    obj_value = pyo.value(ea_model.obj)
    # kp1 = -1/(config.beta*alpha)*math.log(obj_value) if config.beta else obj_value
    kp1 = compute_kp(config, alpha, obj_value) 
    penalty_log.write(f'KP Objective = {kp1:.2f}\n')

    # 3. compute optimal solution excluding penalized sites (model 2)
    ea_model_exclusions = polling_model_factory(dist_df, alpha, config, exclude_penalized_sites=True)
    if log:
        print(f'Model 2 (excludes penalized sites) built for {run_prefix}')

    solve_model(ea_model_exclusions, config.time_limit, log=log, log_file_path=get_log_path(config,'model2'))
    if log:
        print(f'Model 2 solved for {run_prefix}.')

    # 4. convert objective value to KP score (kp2)
    obj_value_exclusions = pyo.value(ea_model_exclusions.obj)
    kp2 = compute_kp(config, alpha, obj_value_exclusions) 

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
    penalized_sites = set(dist_df.loc[dist_df['location_type'].isin(config.penalized_sites), 'id_dest'].unique())
    penalized_selections = penalized_sites.intersection(selected_sites)
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
