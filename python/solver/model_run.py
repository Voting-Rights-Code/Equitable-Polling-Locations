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
from python.utils.constants import LOCATION_SOURCE_CSV, RESULTS_BASE_DIR

from .constants import LOC_ID_DEST, LOC_ID_ORIG

from .run_setup import RunSetup

from .model_config import PollingModelConfig
from .model_data import (
    build_source,
    clean_data,
    alpha_min,
    get_polling_locations,
)
from .model_factory import polling_model_factory
from .model_penalties import PenalizeModel
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

def prepare_run(config: PollingModelConfig, log: bool=False) -> RunSetup:
    '''
    Use a PollingModelConfig to setup everything that is needed to run the model and return a
    RunSetup object with the results.
    '''

    run_prefix = f'{config.config_set}/{config.config_name}'

    source_path = build_locations_distance_file_path(
        config.census_year,
        config.location,
        config.driving,
        config.log_distance,
    )

    # If we are using local files, build the source data if it doesn't already exist
    if config.location_source == LOCATION_SOURCE_CSV:
        if not os.path.exists(source_path):
            warnings.warn(f'File {source_path} not found. Creating it.')
            build_source(
                location_source=LOCATION_SOURCE_CSV,
                census_year=config.census_year,
                location=config.location,
                driving=config.driving,
                log_distance=config.log_distance,
                map_source_date=config.map_source_date,
                log=log,
            )

    polling_locations = get_polling_locations(
        location_source=config.location_source,
        census_year=config.census_year,
        location=config.location,
        log_distance=config.log_distance,
        driving=config.driving,
    )

    polling_locations_set_id = polling_locations.polling_locations_set_id
    locations_df = polling_locations.polling_locations

    #get main data frame
    dist_df = clean_data(config, locations_df, False, log)

    #get alpha
    alpha_df = clean_data(config, locations_df, True, log)
    alpha = alpha_min(alpha_df)

    #build model
    ea_model = polling_model_factory(dist_df, alpha, config)
    if log:
        print(f'model built for {run_prefix}.')

    return RunSetup(
        locations_df=locations_df,
        polling_locations_set_id=polling_locations_set_id,
        dist_df=dist_df,
        alpha=alpha,
        alpha_df=alpha_df,
        ea_model=ea_model,
        run_prefix=run_prefix,
        config=config,
    )


def run_on_config(config: PollingModelConfig, log: bool=False, outtype: str=OUT_TYPE_DB):
    '''
    The entry point to exectute a pyomo/scip run.
    '''

    run_setup = prepare_run(config, log)

    #solve model
    solve_model(run_setup.ea_model, config.time_limit, log=log, log_file_path=config.log_file_path)

    #incorporate result into main dataframe
    result_df = incorporate_result(run_setup.dist_df, run_setup.ea_model)

    #incorporate site penalties as appropriate
    # result_df = incorporate_penalties(
    #     run_setup.dist_df,
    #     run_setup.alpha,
    #     run_setup.run_prefix,
    #     result_df,
    #     run_setup.ea_model,
    #     config,
    #     log,
    # )

    penalty_model = PenalizeModel(run_setup, result_df)
    result_df = penalty_model.run()

    #calculate the new alpha given this assignment
    alpha_new = alpha_min(result_df)

    #calculate the average distances traveled by each demographic to the assigned precinct
    demographic_prec = demographic_domain_summary(result_df, LOC_ID_DEST)

    #calculate the average distances traveled by each demographic by residence
    demographic_res = demographic_domain_summary(result_df, LOC_ID_ORIG)

    #calculate the average distances (and y_ede if beta !=0) traveled by each demographic
    demographic_ede = demographic_summary(demographic_res, result_df, config.beta, alpha_new)

    if outtype == OUT_TYPE_DB:
        write_results_bigquery(
            config=config,
            polling_locations_set_id=run_setup.polling_locations_set_id,
            result_df=result_df,
            demographic_prec=demographic_prec,
            demographic_res=demographic_res,
            demographic_ede=demographic_ede,
            log=log,
        )
    elif outtype == OUT_TYPE_CSV:
        result_folder = os.path.join(RESULTS_BASE_DIR, f'{config.location}_results')

        file_prefix = f'{config.config_set}.{config.config_name}'

        write_results_csv(
            result_folder,
            file_prefix,
            result_df,
            demographic_prec,
            demographic_res,
            demographic_ede,
         )
    else:
        raise ValueError(f'Unknown out type {outtype}')
