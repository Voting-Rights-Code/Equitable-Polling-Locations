'''
This module contains the PenalizeModel class which manages the process of incorporating penalties
into an existing model run.
'''

import functools
from io import FileIO
from typing import Set
import pandas as pd
import pyomo.environ as pyo
import math

from .model_config import PollingModelConfig

from .model_factory import PollingModel, polling_model_factory
from .model_results import (
    incorporate_result,
    compute_kp_score,
)
from .model_solver import solve_model
from .run_setup import RunSetup

from .constants import (
    LOC_LOCATION_TYPE, LOC_ID_DEST, SOLVER_MODEL2, SOLVER_MODEL3, SOLVER_PENALTY, UTF8
)


def get_log_path(config: PollingModelConfig, specifier: str):
    if config.log_file_path: #Inserted to avoid error when log_file_path empty
        base_path = '.'.join(config.log_file_path.split('.')[0:-1])
        return f'{base_path}.{specifier}.log'


def compute_kp(config: PollingModelConfig, alpha: float, obj_value: float) -> float:
    if config.beta:
        return -1 / (config.beta*alpha) * math.log(obj_value)

    return obj_value


class PenalizeModel:
    ''' A class to manage incorperating penalties into an existing model run '''
    _run_setup: RunSetup
    _result_df: pd.DataFrame

    log: bool = False

    def __init__(self, run_setup: RunSetup, result_df: pd.DataFrame, log=False):
        self._run_setup = run_setup
        self._result_df = result_df
        self.log = log


    @functools.cached_property
    def selected_sites(self) -> Set:
        ''' A set of ids of the destinations from the model run results '''
        return set(self._result_df.id_dest)


    @functools.cached_property
    def penalized_sites(self) -> Set:
        dist_df = self._run_setup.dist_df

        return set(
            dist_df.loc[
                dist_df[LOC_LOCATION_TYPE].isin(self._run_setup.config.penalized_sites),
                LOC_ID_DEST,
            ].unique()
        )


    @functools.cached_property
    def penalized_selections(self) -> Set:
        results = self.selected_sites.intersection(self.penalized_sites)

        self._log_write(f'Selected {len(results)} penalized sites:\n')
        for s in sorted(results):
            self._log_write(f'\t ---> {s}\n')

        return results


    @functools.cached_property
    def kp1(self) -> float:
        obj_value = pyo.value(self._run_setup.ea_model.obj)
        result = compute_kp(
            config=self._run_setup.config,
            alpha=self._run_setup.alpha,
            obj_value=obj_value,
        )
        self._log_write(f'KP1 Objective = {result:.2f}\n')

        return result


    @functools.cached_property
    def kp2(self) -> float:
        '''
        The exclusions objective value to KP score (kp2)
        '''

        obj_value_exclusions = pyo.value(self.ea_model_exclusions.obj)

        result = compute_kp(
            config=self._run_setup.config,
            alpha=self._run_setup.alpha,
            obj_value=obj_value_exclusions,
        )

        self._log_write(f'KP2 Objective = {result:.2f}\n')

        return result


    @functools.cached_property
    def ea_model_exclusions(self) -> PollingModel:
        ''' Optimal solution excluding penalized sites (model 2) '''
        result = polling_model_factory(
            dist_df=self._run_setup.dist_df,
            alpha=self._run_setup.alpha,
            config=self._run_setup.config,
            exclude_penalized_sites=True,
        )
        if self.log:
            print(f'Model 2 (excludes penalized sites) built for {self._run_setup.run_prefix}')

        solve_model(
            model=result,
            time_limit=self._run_setup.config.time_limit,
            log=self.log,
            log_file_path=get_log_path(self._run_setup.config, SOLVER_MODEL2),
        )

        if self.log:
            print(f'Model 2 solved for {self._run_setup.run_prefix}.')

        return result


    @functools.cached_property
    def penalty(self) -> float:
        '''
        Penalty as (kp2-kp1)/len(selected penalized sites in model 1)
        penalty = (kp2-kp1)/len(penalized_selections)
        '''

        result = (self.kp2 - self.kp1) / len(self.penalized_selections)
        if self.log:
            print(f'{self.kp1 = :.2f}, {self.kp2 = :.2f}')
            print(f'computed penalty is {result:.2f}')

        return result


    @functools.cached_property
    def ea_model_penalized(self) -> PollingModel:
        result = polling_model_factory(
            dist_df=self._run_setup.dist_df,
            alpha=self._run_setup.alpha,
            config=self._run_setup.config,
            exclude_penalized_sites=False,
            site_penalty=self.penalty,
            kp_penalty_parameter=self.kp1,
        )

        if self.log:
            print(f'Model 3 (penalized model) built for {self._run_setup.run_prefix}.')

        solve_model(
            model=result,
            time_limit=self._run_setup.config.time_limit,
            log=self.log,
            log_file_path=get_log_path(self._run_setup.config, SOLVER_MODEL3),
        )

        if self.log:
            print(f'Model 3 solved for {self._run_setup.run_prefix}.')

        return result


    @functools.cached_property
    def penalized_result_df(self) -> pd.DataFrame:
        ''' Optimal solution including penalized sites applying calculate penalty (model 3) '''

        result = incorporate_result(
            dist_df=self._run_setup.dist_df,
            model=self.ea_model_penalized,
        )

        return result


    @functools.cached_property
    def selected_penalized_result_sites(self) -> Set:
        return set(self.penalized_result_df.id_dest)


    @functools.cached_property
    def penalized_result_selections(self) -> Set:
        result = self.penalized_sites.intersection(self.selected_penalized_result_sites)

        self._log_write('\nModel 3: penalized model\n')
        self._log_write(f'Penalty applied to each site = {self.penalty:.2f}\n')

        if result:
            self._log_write(f'Selected {len(result)} penalized sites:\n')
            for s in sorted(result):
                self._log_write(f'\t ---> {s}\n')
        else:
            self._log_write('Selected no penalized sites.\n')

        return result


    @functools.cached_property
    def kp_pen(self) -> float:
        obj_value = pyo.value(self.ea_model_penalized.obj)
        result = compute_kp(
            config=self._run_setup.config,
            alpha=self._run_setup.alpha,
            obj_value=obj_value,
        )

        self._log_write(f'Penalized KP Optimal = {result:.2f}\n')

        return result


    @functools.cached_property
    def optimal_kp(self) -> float:
        result = compute_kp_score(
            df=self.penalized_result_df,
            beta=self._run_setup.config.beta,
            alpha=self._run_setup.alpha,
        )

        self._log_write(f'KP Optimal = {result:.2f}\n')

        return result


    def _report_final_statistics(self):
        self._log_write(f'Penalty = {self.kp_pen-self.optimal_kp:.2f}\n')


    @functools.cached_property
    def _penalty_log_file(self) -> FileIO:
        return open(
            get_log_path(self._run_setup.config, SOLVER_PENALTY),
            'a',
            encoding=UTF8,
        )


    def _log_write(self, message: str):
        if self.log:
            self._penalty_log_file.write(message)


    def _close_log(self):
        # Check if the log is available without causing it to evaluate
        if '_penalty_log' in self.__dict__:
            self._penalty_log_file.close()
            del self._penalty_log_file


    def run(self) -> pd.DataFrame:
        ''' Computes the new results incorporating penalties '''

        #check if this is a penalized run
        if not self._run_setup.config.penalized_sites:
            return self._result_df

        try:
            self._log_write('Model 1: original model with no penalties\n')
            # self._check_if_penalized_sites_selected()
            if not self.penalized_selections:
                self._log_write('No penalized sites selected')
                return self._result_df

            self._report_final_statistics()

            return self.penalized_result_df

        finally:
            self._close_log()
