'''
This file sets up a pyomo/scip run based on a config instance
'''

import os
import warnings
import functools

import pandas as pd

from .model_solver import solve_model

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
from .model_factory import PollingModel, polling_model_factory
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

class ModelRun():
    '''
    A class to manage the process of running a model based on a PollingModelConfig.
    This is the main entry point for running models.
    '''

    _config: PollingModelConfig
    _log: bool

    def __init__(self, config: PollingModelConfig, log: bool=False):
        self._config = config
        self._log = log


    @functools.cached_property
    def _query(self) -> Query:
        ''' An isntance of Query for database operations based on the config environment. '''
        return Query(self._config.environment)


    @functools.cached_property
    def _solved_ea_model(self) -> PollingModel:
        '''
        The solved ea_model.

        This cached property builds and solves the model, returning the solved PollingModel instance.
        '''

        solve_model(
            model=self.run_setup.ea_model,
            time_limit=self._config.time_limit,
            log=self._log,
            log_file_path=self._config.log_file_path,
        )

        return self.run_setup.ea_model


    @functools.cached_property
    def _initial_result_df(self):
        '''
        The raw result DataFrame from the solved model containing only the matched residences
        and precinct, before penalties are applied.
        '''

        return incorporate_result(
            dist_df=self.run_setup.dist_df,
            model=self._solved_ea_model,
        )


    @functools.cached_property
    def result_df(self):
        ''' The final result DataFrame from the solved model after penalties are applied.'''
        penalty_model = PenalizeModel(
            run_setup=self.run_setup,
            result_df=self._initial_result_df,
        )
        return penalty_model.run()


    @functools.cached_property
    def _alpha_new(self) -> float:
        ''' The new alpha given this assignment '''
        return alpha_min(self.result_df)


    @functools.cached_property
    def demographic_prec(self) -> pd.DataFrame:
        ''' The calculate average distances traveled by each demographic to the assigned precinct '''
        return demographic_domain_summary(self.result_df, LOC_ID_DEST)


    @functools.cached_property
    def demographic_res(self) -> pd.DataFrame:
        ''' The calculated average distances traveled by each demographic by residence '''
        return demographic_domain_summary(self.result_df, LOC_ID_ORIG)


    @functools.cached_property
    def demographic_edes(self) -> pd.DataFrame:
        ''' The calculated average distances (and y_ede if beta !=0) traveled by each demographic '''
        return demographic_summary(
            self.demographic_res,
            self.result_df,
            self._config.beta,
            self._alpha_new,
        )


    @functools.cached_property
    def run_setup(self) -> RunSetup:
        '''
        An instance of RunSetup that contains everything needed, including source data, to run the
        pyo model based on the PollingModelConfig.
        '''

        run_prefix = f'{self._config.config_set}/{self._config.config_name}'

        source_path = build_locations_distance_file_path(
            self._config.census_year,
            self._config.location,
            self._config.driving,
            self._config.log_distance,
        )

        # Default to query being None to avoid unnecessary opening database connections
        query: Query=None

        # If we are using local files, build the source data if it doesn't already exist
        if self._config.data_source == DATA_SOURCE_CSV:
            # Check if the local source file exists for get_polling_locations, if it doesn't then build it
            if not os.path.exists(source_path):
                warnings.warn(f'File {source_path} not found. Creating it.')
                build_source(
                    data_source=DATA_SOURCE_CSV,
                    census_year=self._config.census_year,
                    location=self._config.location,
                    driving=self._config.driving,
                    log_distance=self._config.log_distance,
                    map_source_date=self._config.map_source_date,
                    log=self._log,
                )
        else:
            # Force evaluates _query to create a Query instance in order to get the polling locations from the database
            query = self._query

        polling_locations = get_polling_locations(
            data_source=self._config.data_source,
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
        ''' Writes the model run results to the database configured in the environment specified in the config.'''
        write_results_bigquery(
            config=self._config,
            query=self._query,
            polling_locations_set_id=self.run_setup.polling_locations_set_id,
            result_df=self.result_df,
            demographic_prec=self.demographic_prec,
            demographic_res=self.demographic_res,
            demographic_ede=self.demographic_ede,
            log=self._log,
        )


    def write_results_csv(self):
        ''' Writes the model run results to CSV files in the results directory.'''
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

