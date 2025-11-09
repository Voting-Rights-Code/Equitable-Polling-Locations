'''
This file sets up a pyomo/scip run based on a config instance
'''

import os
import warnings
import functools

import pyomo.environ as pyo
import pandas as pd

from python.database.query import Query
from python.utils import build_locations_distance_file_path
from python.utils.directory_constants import RESULTS_BASE_DIR

from .constants import LOC_ID_DEST, LOC_ID_ORIG, DATA_SOURCE_CSV

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

OUT_TYPE_DB = 'db'
OUT_TYPE_CSV = 'csv'

SOLVER_NAME = 'scip'
LIMITS_GAP = 0.02
LP_THREADS = 2


class ModelRun():
    '''
    A class to manage the process of running a model based on a PollingModelConfig.
    This is the main entry point for running models.
    '''

    # result_df: pd.DataFrame
    # demographic_prec: pd.DataFrame
    # demographic_res: pd.DataFrame
    # demographic_ede: pd.DataFrame

    def __init__(self, config: PollingModelConfig, log: bool=False):
        self._config = config
        self._log = log
        self._run_prefix = f'{config.config_set}/{config.config_name}'

        self._source_path = build_locations_distance_file_path(
            self._config.census_year,
            self._config.location,
            self._config.driving,
            self._config.log_distance,
        )

    @functools.cached_property
    def _query(self) -> Query:
        return Query(self._config.environment)

    @functools.cached_property
    def _ea_model(self) -> pyo.ConcreteModel:
        ''' This funciton will execute scip '''
        #define solver
        solver = pyo.SolverFactory(SOLVER_NAME)
        solver.options = { 'limits/time': self._config.time_limit,  'limits/gap': LIMITS_GAP, 'lp/threads': LP_THREADS }

        solver.solve(
            self._run_setup.ea_model,
            tee=self._log,
            logfile=self._config.log_file_path,
        )

        return self._run_setup.ea_model

    @functools.cached_property
    def _raw_result_df(self):
        return incorporate_result(self._run_setup.dist_df, self._ea_model)

    @functools.cached_property
    def result_df(self):
        penalty_model = PenalizeModel(
            run_setup=self._run_setup,
            result_df=self._raw_result_df,
        )
        return penalty_model.run()

    @functools.cached_property
    def _alpha_new(self) -> float:
        ''' calculate the new alpha given this assignment '''
        return alpha_min(self.result_df)

    @functools.cached_property
    def demographic_prec(self) -> pd.DataFrame:
        ''' Calculate the average distances traveled by each demographic to the assigned precinct '''
        return demographic_domain_summary(self.result_df, LOC_ID_DEST)

    @functools.cached_property
    def demographic_res(self) -> pd.DataFrame:
        ''' calculate the average distances traveled by each demographic by residence '''
        return demographic_domain_summary(self.result_df, LOC_ID_ORIG)

    @functools.cached_property
    def demographic_ede(self) -> pd.DataFrame:
        ''' calculate the average distances (and y_ede if beta !=0) traveled by each demographic '''
        return demographic_summary(
            self.demographic_res,
            self.result_df,
            self._config.beta,
            self._alpha_new,
        )

    @functools.cached_property
    def _run_setup(self) -> RunSetup:
        '''
        Use a PollingModelConfig to setup everything that is needed to run the model and return a
        RunSetup object with the results.
        '''

        run_prefix = f'{self._config.config_set}/{self._config.config_name}'

        source_path = build_locations_distance_file_path(
            self._config.census_year,
            self._config.location,
            self._config.driving,
            self._config.log_distance,
        )

        query: Query=None

        # If we are using local files, build the source data if it doesn't already exist
        if self._config.location_source == DATA_SOURCE_CSV:
            if not os.path.exists(source_path):
                warnings.warn(f'File {source_path} not found. Creating it.')
                build_source(
                    location_source=DATA_SOURCE_CSV,
                    census_year=self._config.census_year,
                    location=self._config.location,
                    driving=self._config.driving,
                    log_distance=self._config.log_distance,
                    map_source_date=self._config.map_source_date,
                    log=self._log,
                )
        else:
            query = self._query

        polling_locations = get_polling_locations(
            location_source=self._config.location_source,
            census_year=self._config.census_year,
            location=self._config.location,
            log_distance=self._config.log_distance,
            driving=self._config.driving,
            query=query,
            log=self._log,
        )

        polling_locations_set_id = polling_locations.polling_locations_set_id
        locations_df = polling_locations.polling_locations

        #get main data frame
        dist_df = clean_data(self._config, locations_df, False, self._log)

        #get alpha
        alpha_df = clean_data(self._config, locations_df, True, self._log)
        alpha = alpha_min(alpha_df)

        #build model
        ea_model = polling_model_factory(dist_df, alpha, self._config)
        if self._log:
            print(f'model built for {run_prefix}.')

        return RunSetup(
            locations_df=locations_df,
            polling_locations_set_id=polling_locations_set_id,
            dist_df=dist_df,
            alpha=alpha,
            alpha_df=alpha_df,
            ea_model=ea_model,
            run_prefix=run_prefix,
            config=self._config,
        )

    def write_results_db(self):
        write_results_bigquery(
            config=self._config,
            query=self._query,
            polling_locations_set_id=self._run_setup.polling_locations_set_id,
            result_df=self.result_df,
            demographic_prec=self.demographic_prec,
            demographic_res=self.demographic_res,
            demographic_ede=self.demographic_ede,
            log=self._log,
        )

    def write_results_csv(self):
        result_folder = os.path.join(RESULTS_BASE_DIR, f'{self._config.location}_results')

        file_prefix = f'{self._config.config_set}.{self._config.config_name}'

        write_results_csv(
            result_folder=result_folder,
            file_prefix=file_prefix,
            result_df=self.result_df,
            demographic_prec=self.demographic_prec,
            demographic_res=self.demographic_res,
            demographic_ede=self.demographic_ede,
        )









# def prepare_run(config: PollingModelConfig, log: bool=False) -> RunSetup:
#     '''
#     Use a PollingModelConfig to setup everything that is needed to run the model and return a
#     RunSetup object with the results.
#     '''

#     run_prefix = f'{config.config_set}/{config.config_name}'

#     source_path = build_locations_distance_file_path(
#         config.census_year,
#         config.location,
#         config.driving,
#         config.log_distance,
#     )

#     query: Query = None
#     # If we are using local files, build the source data if it doesn't already exist
#     if config.location_source == DATA_SOURCE_CSV:
#         if not os.path.exists(source_path):
#             warnings.warn(f'File {source_path} not found. Creating it.')
#             build_source(
#                 location_source=DATA_SOURCE_CSV,
#                 census_year=config.census_year,
#                 location=config.location,
#                 driving=config.driving,
#                 log_distance=config.log_distance,
#                 map_source_date=config.map_source_date,
#                 log=log,
#             )
#     else:
#         query = Query(config.environment)

#     polling_locations = get_polling_locations(
#         location_source=config.location_source,
#         census_year=config.census_year,
#         location=config.location,
#         log_distance=config.log_distance,
#         driving=config.driving,
#         query=query,
#         log=log,
#     )

#     polling_locations_set_id = polling_locations.polling_locations_set_id
#     locations_df = polling_locations.polling_locations

#     #get main data frame
#     dist_df = clean_data(config, locations_df, False, log)

#     #get alpha
#     alpha_df = clean_data(config, locations_df, True, log)
#     alpha = alpha_min(alpha_df)

#     #build model
#     ea_model = polling_model_factory(dist_df, alpha, config)
#     if log:
#         print(f'model built for {run_prefix}.')

#     return RunSetup(
#         locations_df=locations_df,
#         polling_locations_set_id=polling_locations_set_id,
#         dist_df=dist_df,
#         alpha=alpha,
#         alpha_df=alpha_df,
#         ea_model=ea_model,
#         run_prefix=run_prefix,
#         config=config,
#     )

#################################

# def run_on_config(config: PollingModelConfig, log: bool=False, outtype: str=OUT_TYPE_DB):
#     '''
#     The entry point to exectute a pyomo/scip run.
#     '''

#     run_setup = prepare_run(config, log)

#     #solve model
#     solve_model(run_setup.ea_model, config.time_limit, log=log, log_file_path=config.log_file_path)

#     #incorporate result into main dataframe
#     result_df = incorporate_result(run_setup.dist_df, run_setup.ea_model)

#     #incorporate site penalties as appropriate
#     # result_df = incorporate_penalties(
#     #     run_setup.dist_df,
#     #     run_setup.alpha,
#     #     run_setup.run_prefix,
#     #     result_df,
#     #     run_setup.ea_model,
#     #     config,
#     #     log,
#     # )

#     penalty_model = PenalizeModel(run_setup, result_df)
#     result_df = penalty_model.run()

#     #calculate the new alpha given this assignment
#     alpha_new = alpha_min(result_df)

#     #calculate the average distances traveled by each demographic to the assigned precinct
#     demographic_prec = demographic_domain_summary(result_df, LOC_ID_DEST)

#     #calculate the average distances traveled by each demographic by residence
#     demographic_res = demographic_domain_summary(result_df, LOC_ID_ORIG)

#     #calculate the average distances (and y_ede if beta !=0) traveled by each demographic
#     demographic_ede = demographic_summary(demographic_res, result_df, config.beta, alpha_new)

    # if outtype == OUT_TYPE_DB:
    #     query = Query(config.environment)
    #     write_results_bigquery(
    #         config=config,
    #         query=query,
    #         polling_locations_set_id=run_setup.polling_locations_set_id,
    #         result_df=result_df,
    #         demographic_prec=demographic_prec,
    #         demographic_res=demographic_res,
    #         demographic_ede=demographic_ede,
    #         log=log,
    #     )
    # elif outtype == OUT_TYPE_CSV:
    #     result_folder = os.path.join(RESULTS_BASE_DIR, f'{config.location}_results')

#         file_prefix = f'{config.config_set}.{config.config_name}'

#         write_results_csv(
#             result_folder,
#             file_prefix,
#             result_df,
#             demographic_prec,
#             demographic_res,
#             demographic_ede,
#          )
#     else:
#         raise ValueError(f'Unknown out type {outtype}')
