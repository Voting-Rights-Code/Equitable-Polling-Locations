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


def get_log_path(config: PollingModelConfig, specifier: str):
    if config.log_file_path: #Inserted to avoid error when log_file_path empty
        base_path = '.'.join(config.log_file_path.split('.')[0:-1])
        return f'{base_path}.{specifier}.log'


def compute_kp(config: PollingModelConfig, alpha: float, obj_value: float) -> float:
    if config.beta:
        return -1/(config.beta*alpha)*math.log(obj_value)

    return obj_value

@dataclass
class PenalizeModel:
    ''' A class to manage incorperating penalties into an existing model run '''
    run_setup: RunSetup
    result_df: pd.DataFrame

    log: bool = False

    selected_sites: Set = None
    penalized_sites: Set = None
    penalized_selections: Set = None

    obj_value: float = None
    kp1: float = None
    kp2: float = None

    penalty: float = None

    ea_model_exclusions: PollingModel = None
    ea_model_penalized: PollingModel = None

    penalized_result_df: pd.DataFrame = None

    penalty_log: TextIOWrapper = None

    def _check_if_penalized_sites_selected(self):
        dist_df = self.run_setup.dist_df
        config = self.run_setup.config

        self.selected_sites = set(self.result_df.id_dest)
        self.penalized_sites = set(dist_df.loc[dist_df['location_type'].isin(config.penalized_sites), 'id_dest'].unique())
        self.penalized_selections = self.selected_sites.intersection(self.penalized_sites)

        self._log_write(f'Selected {len(self.penalized_selections)} penalized sites:\n')
        for s in sorted(self.penalized_selections):
            self._log_write(f'\t ---> {s}\n')


    def _compute_kp1(self):
        '''
        Convert objective value to KP score (kp1)
        '''

        self.obj_value = pyo.value(self.run_setup.ea_model.obj)
        self.kp1 = compute_kp(self.run_setup.config, self.run_setup.alpha, self.obj_value)
        self._log_write(f'KP Objective = {self.kp1:.2f}\n')


    def _compute_optimal_solution(self):
        '''
        Compute optimal solution excluding penalized sites (model 2)
        '''
        config = self.run_setup.config

        self.ea_model_exclusions = polling_model_factory(
            self.run_setup.dist_df,
            self.run_setup.alpha,
            config,
            exclude_penalized_sites=True
        )
        if self.log:
            print(f'Model 2 (excludes penalized sites) built for {self.run_prefix}')

        solve_model(
            self.ea_model_exclusions,
            config.time_limit,
            log=self.log,
            log_file_path=get_log_path(self.run_setup.config,'model2'))

        if self.log:
            print(f'Model 2 solved for {self.run_prefix}.')


    def _compute_kp2(self):
        '''
        Convert the exclusions objective value to KP score (kp2)
        '''

        self.obj_value_exclusions = pyo.value(self.ea_model_exclusions.obj)

        self.kp2 = compute_kp(
            self.run_setup.config,
            self.run_setup.alpha,
            self.obj_value_exclusions,
        )


    def _compute_penalty(self):
        '''
        Compute penalty as (kp2-kp1)/len(selected penalized sites in model 1)
        penalty = (kp2-kp1)/len(penalized_selections)
        '''

        self.penalty = (self.kp2-self.kp1)/len(self.penalized_selections)
        if self.log:
            print(f'{self.kp1 = :.2f}, {self.kp2 = :.2f}')
            print(f'computed penalty is {self.penalty:.2f}')


    def _compute_penalized_optimal_solution(self):
        '''
        compute optimal solution including penalized sites applying calculate penalty (model 3)
        '''

        config = self.run_setup.config
        dist_df = self.run_setup.dist_df
        alpha = self.run_setup.alpha

        self.ea_model_penalized = polling_model_factory(
            dist_df, alpha, config,
            exclude_penalized_sites=False,
            site_penalty=self.penalty,
            kp_penalty_parameter=self.kp1,
        )

        if self.log:
            # final_model = ('penalized', ea_model_penalized)
            print(f'Model 3 (penalized model) built for {self.run_prefix}.')

        solve_model(self.ea_model_penalized, config.time_limit, log=self.log, log_file_path=get_log_path(config,'model3'))

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
        config = self.run_setup.config
        alpha = self.run_setup.alpha

        # TODO make these results class variables for testing?
        obj_value = pyo.value(self.ea_model_penalized.obj)
        kp_pen = -1/(config.beta*alpha)*math.log(obj_value) if config.beta else obj_value
        kp = compute_kp_score(self.penalized_result_df, config.beta, alpha=alpha)

        self._log_write(f'Penalized KP Optimal = {kp_pen:.2f}\n')
        self._log_write(f'KP Optimal = {kp:.2f}\n')
        self._log_write(f'Penalty = {kp_pen-kp:.2f}\n')


    def _setup_log(self):
        '''
        Opens a log file for appending output to if there is a log_file_path configured
        in the config instance.
        '''

        if self.run_setup.config.log_file_path:
            self.penalty_log = open(get_log_path(self.run_setup.config,'penalty'), 'a', encoding='utf-8')


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
        if not self.run_setup.config.penalized_sites:
            return self.result_df

        self._setup_log()

        try:
            self._log_write('Model 1: original model with no penalties\n')
            self._check_if_penalized_sites_selected()
            if not self.penalized_selections:
                print('No penalized sites selected')
                return self.result_df
 
            self._compute_kp1()
            self._compute_optimal_solution()
            self._compute_kp2()
            self._compute_penalty()
            self._compute_penalized_optimal_solution()

            self._report_final_statistics()

            return self.penalized_result_df

        finally:
            self._close_log()



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
