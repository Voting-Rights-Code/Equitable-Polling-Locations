'''
This module contains the PenalizeModel class which manages the process of incorporating penalties
into an existing model run.
'''

from dataclasses import dataclass
from io import TextIOWrapper
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
    LOC_LOCATION_TYPE, LOC_ID_DEST, SOLVER_MODEL2, SOLVER_PENALTY, UTF8
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

    selected_sites: Set = None
    penalized_sites: Set = None
    penalized_selections: Set = None

    #obj_value: float = None  #this is an internal value that gets called then dropped
    kp1: float = None
    kp2: float = None
    kp_pen: float = None
    optimal_kp: float = None

    penalty: float = None

    ea_model_exclusions: PollingModel = None
    ea_model_penalized: PollingModel = None

    penalized_result_df: pd.DataFrame = None

    penalty_log: TextIOWrapper = None

    def __init__(self, run_setup: RunSetup, result_df: pd.DataFrame):
        self._run_setup = run_setup
        self._result_df = result_df

    def _check_if_penalized_sites_selected(self):
        dist_df = self._run_setup.dist_df
        config = self._run_setup.config

        self.selected_sites = set(self._result_df.id_dest)
        self.penalized_sites = set(
            dist_df.loc[dist_df[LOC_LOCATION_TYPE].isin(config.penalized_sites), LOC_ID_DEST].unique()
        )
        self.penalized_selections = self.selected_sites.intersection(self.penalized_sites)

        self._log_write(f'Selected {len(self.penalized_selections)} penalized sites:\n')
        for s in sorted(self.penalized_selections):
            self._log_write(f'\t ---> {s}\n')


    def _compute_kp1(self):
        '''
        Convert objective value to KP score (kp1)
        '''

        obj_value = pyo.value(self._run_setup.ea_model.obj)
        self.kp1 = compute_kp(self._run_setup.config, self._run_setup.alpha, obj_value)
        self._log_write(f'KP Objective = {self.kp1:.2f}\n')


    def _compute_optimal_solution(self):
        '''
        Compute optimal solution excluding penalized sites (model 2)
        '''
        config = self._run_setup.config

        self.ea_model_exclusions = polling_model_factory(
            self._run_setup.dist_df,
            self._run_setup.alpha,
            config,
            exclude_penalized_sites=True,
        )
        if self.log:
            print(f'Model 2 (excludes penalized sites) built for {self.run_prefix}')

        solve_model(
            self.ea_model_exclusions,
            config.time_limit,
            log=self.log,
            log_file_path=get_log_path(self._run_setup.config, SOLVER_MODEL2),
        )

        if self.log:
            print(f'Model 2 solved for {self.run_prefix}.')


    def _compute_kp2(self):
        '''
        Convert the exclusions objective value to KP score (kp2)
        '''

        obj_value_exclusions = pyo.value(self.ea_model_exclusions.obj)

        self.kp2 = compute_kp(
            self._run_setup.config,
            self._run_setup.alpha,
            obj_value_exclusions,
        )


    def _compute_penalty(self):
        '''
        Compute penalty as (kp2-kp1)/len(selected penalized sites in model 1)
        penalty = (kp2-kp1)/len(penalized_selections)
        '''

        self.penalty = (self.kp2-self.kp1) / len(self.penalized_selections)
        if self.log:
            print(f'{self.kp1 = :.2f}, {self.kp2 = :.2f}')
            print(f'computed penalty is {self.penalty:.2f}')


    def _compute_penalized_optimal_solution(self):
        '''
        compute optimal solution including penalized sites applying calculate penalty (model 3)
        '''

        config = self._run_setup.config
        dist_df = self._run_setup.dist_df
        alpha = self._run_setup.alpha

        self.ea_model_penalized = polling_model_factory(
            dist_df, alpha, config,
            exclude_penalized_sites=False,
            site_penalty=self.penalty,
            kp_penalty_parameter=self.kp1,
        )

        if self.log:
            # final_model = ('penalized', ea_model_penalized)
            print(f'Model 3 (penalized model) built for {self.run_prefix}.')

        solve_model(
            self.ea_model_penalized, config.time_limit,
            log=self.log, log_file_path=get_log_path(config,'model3'),
        )

        if self.log:
            print(f'Model 3 solved for {self.run_prefix}.')

        self.penalized_result_df = incorporate_result(dist_df, self.ea_model_penalized)

        # TODO clean this up - overlapping vairable names / confusing esp penalized_selections and selected_sites
        selected_sites = set(self.penalized_result_df.id_dest)
        penalized_selections = self.penalized_sites.intersection(selected_sites)

        self._log_write('\nModel 3: penalized model\n')
        self._log_write(f'Penalty applied to each site = {self.penalty:.2f}\n')

        if penalized_selections:
            self._log_write(f'Selected {len(penalized_selections)} penalized sites:\n')
            for s in sorted(penalized_selections):
                self._log_write(f'\t ---> {s}\n')
        else:
            self._log_write('Selected no penalized sites.\n')


    def _report_final_statistics(self):
        config = self._run_setup.config
        alpha = self._run_setup.alpha

        # TODO make these results class variables for testing?
        obj_value = pyo.value(self.ea_model_penalized.obj)
        self.kp_pen = compute_kp(
            self._run_setup.config,
            self._run_setup.alpha,
            obj_value,
        )

        self.optimal_kp = compute_kp_score(self.penalized_result_df, config.beta, alpha=alpha)

        self._log_write(f'Penalized KP Optimal = {self.kp_pen:.2f}\n')
        self._log_write(f'KP Optimal = {self.optimal_kp:.2f}\n')
        self._log_write(f'Penalty = {self.kp_pen-self.optimal_kp:.2f}\n')


    def _setup_log(self):
        '''
        Opens a log file for appending output to if there is a log_file_path configured
        in the config instance.
        '''

        if self._run_setup.config.log_file_path:
            self.penalty_log = open(
                get_log_path(self._run_setup.config, SOLVER_PENALTY),
                'a',
                encoding=UTF8,
            )


    def _log_write(self, message: str):
        if self.penalty_log:
            self.penalty_log.write(message)


    def _close_log(self):
        if self.penalty_log:
            self.penalty_log.close()
            self.penalty_log = None


    def run(self) -> pd.DataFrame:
        ''' Computes the new results incorporating penalties '''

        #check if this is a penalized run
        if not self._run_setup.config.penalized_sites:
            return self._result_df

        self._setup_log()

        try:
            self._log_write('Model 1: original model with no penalties\n')
            self._check_if_penalized_sites_selected()
            if not self.penalized_selections:
                print('No penalized sites selected')
                return self._result_df

            self._compute_kp1()
            self._compute_optimal_solution()
            self._compute_kp2()
            self._compute_penalty()
            self._compute_penalized_optimal_solution()

            self._report_final_statistics()

            return self.penalized_result_df

        finally:
            self._close_log()
