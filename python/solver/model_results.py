'''
Various utility methods to process the output of a model run
'''

import math
import os
import threading

import numpy as np
import pandas as pd

import pyomo.environ as pyo

from python.database import imports
from python.database.query import Query

from python.utils import (
  timer,
  current_time_utc,
  build_results_file_path,
  build_precinct_summary_file_path,
  build_residence_summary_file_path,
  build_y_ede_summary_file_path
)

# pylint: disable-next=wildcard-import,unused-wildcard-import
from .constants import *

from .model_config import PollingModelConfig


lock = threading.Lock()

@timer
def incorporate_result(dist_df: pd.DataFrame, model: pyo.ConcreteModel, log_distance: bool):
    '''Input: dist_df--the main data frame containing the data for model
              model -- the solved model
              model.matching -- pyo boolean variable for when a residence is matched to a precinct (res, prec):bool
    output: dataframe containing only the matched residences and precincts'''

    #turn matched solution into df
    matching_list= [(key[0], key[1], model.matching[key].value) for key in model.matching]
    matching_df = pd.DataFrame(matching_list, columns = [LOC_ID_ORIG, LOC_ID_DEST, RESULT_MATCHING])

    #the matching doesn't always give an integer value. Replace the value with the integer it would round to   
    matching_df[RESULT_MATCHING].mask(matching_df[RESULT_MATCHING] >= 0.5, 1, inplace=True)
    matching_df[RESULT_MATCHING].mask(matching_df[RESULT_MATCHING] < 0.5, 0, inplace=True)

    #merge with dist_df
    result_df = pd.merge(dist_df, matching_df, on=[LOC_ID_ORIG, LOC_ID_DEST])

    #keep only pairs that have been matched
    #if no matches, raise error
    if all(result_df[RESULT_MATCHING].isnull()):
        raise ValueError('The model has no matched precincts')
    if any(result_df[RESULT_MATCHING].isnull()):
        raise ValueError('The model has some unmatched precincts')
    result_df = result_df.loc[result_df[RESULT_MATCHING] == 1]
    if log_distance:
        result_df[LOC_DISTANCE_M] = math.e**result_df[LOC_DISTANCE_M]

    return result_df

@timer
def demographic_domain_summary(result_df: pd.DataFrame, domain: str):
    '''Input: result_df-- the distance an demographic population data for the matched residences and precincts
        domain-- [ID_DEST, ID_ORIG] either the precinct of residence
    Output: Calculate the average distances traveled by each demographic group that is assigned to each precinct
        or that lives in each residence.'''

    if domain not in [LOC_ID_DEST, LOC_ID_ORIG]:
        raise ValueError('domain much be in [id_dest, id_orig]')
    #extract unique source value for later
    source_value = result_df[LOC_SOURCE].unique()
    #Transform to get distance and population by demographic, destination pairs for each origin
    demographic_all = pd.melt(
        result_df[[
            domain, LOC_DISTANCE_M, LOC_TOTAL_POPULATION, LOC_WHITE, LOC_BLACK, LOC_NATIVE, LOC_ASIAN, LOC_HISPANIC,
        ]],
        id_vars=[domain, LOC_DISTANCE_M],
        value_vars=[LOC_TOTAL_POPULATION, LOC_WHITE, LOC_BLACK, LOC_NATIVE, LOC_ASIAN, LOC_HISPANIC],
        var_name=RESULT_DEMOGRAPHIC,
        value_name=RESULT_DEMO_POP,
    )

    #create a weighted distance column for people of each demographic
    demographic_all[DOMAIN_WEIGHTED_DIST] = demographic_all[RESULT_DEMO_POP] * demographic_all[LOC_DISTANCE_M]

    #calculate the total population of each demographic sent to each precinct
    demographic_pop = demographic_all[
        [domain, RESULT_DEMOGRAPHIC, RESULT_DEMO_POP]
    ].groupby([domain, RESULT_DEMOGRAPHIC]).agg(PD_SUM)

    #calculate the total distance traveled by each demographic group
    demographic_dist = demographic_all[
        [domain, RESULT_DEMOGRAPHIC, DOMAIN_WEIGHTED_DIST]
    ].groupby([domain, RESULT_DEMOGRAPHIC]).agg(PD_SUM)

    #merge the demographic_pop and demographic_dist
    demographic_prec = pd.concat([demographic_dist, demographic_pop], axis=1)

    #calculate the average distance
    demographic_prec[RESULT_AVG_DIST] = demographic_prec[DOMAIN_WEIGHTED_DIST] / demographic_prec[RESULT_DEMO_POP]

    #add source data back in
    demographic_prec[LOC_SOURCE] = source_value[0]

    return demographic_prec

@timer
def demographic_summary(demographic_df: pd.DataFrame, result_df: pd.DataFrame, beta: float, alpha: float):
    '''Input: demographic_df-- the distance an demographic population data for the matched residences and precincts
    beta -- the inequality aversion factor
    alpha -- the data derived normalization factor
    Output: Calculate the average distances traveled by each demographic group.'''

    #extract unique source value for later
    source_value = result_df[LOC_SOURCE].unique()

    #calculate the total distance traveled by each demographic group
    demographic_dist = demographic_df[DOMAIN_WEIGHTED_DIST].groupby(RESULT_DEMOGRAPHIC).agg(PD_SUM)

    #calculate the total population of each demographic sent to each precinct
    demographic_population = demographic_df[RESULT_DEMO_POP].groupby(RESULT_DEMOGRAPHIC).agg(PD_SUM)

    #merge the datasets
    result = pd.concat([demographic_dist, demographic_population], axis=1)

    #for base line comparison, or if config.beta ==0
    result[RESULT_AVG_DIST] = result[DOMAIN_WEIGHTED_DIST] / result[RESULT_DEMO_POP]

    if beta !=0:
        #add the distance_m column back in from dist_df
        #1) first make demographics a column, not an index
        demographic_by_res = demographic_df.reset_index([RESULT_DEMOGRAPHIC])
        #2) set index for results to ID_ORIG
        distances = result_df[[LOC_ID_ORIG, LOC_DISTANCE_M]].set_index(LOC_ID_ORIG)
        #3) merge on id_orig (index for both)
        demographics = demographic_by_res.merge(
            distances,
            left_index=True,
            right_index=True,
            how=PD_OUTER,
        )

        #add in a KP factor column
        demographics[RESULT_KP_FACTOR] = math.e ** (-beta * alpha * demographics[LOC_DISTANCE_M])
        #calculate the summand for the objective function
        demographics[RESULT_DEMO_RES_OBJ_SUMMAND] = demographics[RESULT_DEMO_POP] * demographics[RESULT_KP_FACTOR]

        #compute the ede for each demographic group
        demographic_ede = demographics[
            [RESULT_DEMOGRAPHIC, RESULT_DEMO_RES_OBJ_SUMMAND, RESULT_DEMO_POP]
        ].groupby(RESULT_DEMOGRAPHIC).agg(PD_SUM)
        demographic_ede[RESULT_AVG_KP_WEIGHT] = (
            demographic_ede.demo_res_obj_summand / demographic_ede.demo_pop
        )
        demographic_ede[RESULT_Y_EDE] = (-1 / (beta * alpha)) * np.log(demographic_ede[RESULT_AVG_KP_WEIGHT])

        #merge the datasets
        result = pd.concat([result[[DOMAIN_WEIGHTED_DIST, RESULT_AVG_DIST]], demographic_ede], axis=1)

    #add source data back in
    result[LOC_SOURCE] = source_value[0]

    return result


@timer
def write_results_csv(
    result_folder: str,
    file_prefix: str,
    result_df: pd.DataFrame,
    demographic_prec: pd.DataFrame,
    demographic_res: pd.DataFrame,
    demographic_ede: pd.DataFrame,
):
    '''Write result, demographic_prec, demographic_res and demographic_ede to local CSV file'''

    # Create result_path as needed
    if not os.path.exists(result_folder):
        os.makedirs(result_folder)

    result_file = build_results_file_path(result_folder, file_prefix)
    precinct_summary_file = build_precinct_summary_file_path(result_folder, file_prefix)
    residence_summary_file = build_residence_summary_file_path(result_folder, file_prefix)
    y_ede_summary_file = build_y_ede_summary_file_path(result_folder, file_prefix)

    result_df.to_csv(result_file, index=True)
    demographic_prec.to_csv(precinct_summary_file, index=True)
    demographic_res.to_csv(residence_summary_file, index=True)
    demographic_ede.to_csv(y_ede_summary_file, index=True)


@timer
def write_results_bigquery(
    config: PollingModelConfig,
    query: Query,
    polling_locations_set_id: str,
    result_df: pd.DataFrame,
    demographic_prec: pd.DataFrame,
    demographic_res: pd.DataFrame,
    demographic_ede: pd.DataFrame,
    log: bool=False,
):
    '''Write result, demographic_prec, demographic_res and demographic_ede to BigQuery SQL tables'''

    environment = config.environment

    # Setup a thread lock so that only one write to bigquery happens at a time.
    # This is to prevent problems with tqdm being used in model_run_cli.py
    with lock:
        if config.db_id:
            # If we already have a database id then assume that the source_config
            # is already written to the database and just use the existing ID
            model_config_id = config.db_id
            config_set = config.config_set
            config_name = config.config_name
        else:
            # With no id, create a new database instance of the source_config
            print(f'source_config.config_file_path: {config.config_file_path}')
            model_config = query.create_db_model_config(config)
            model_config = query.find_or_create_model_config(model_config)

            model_config_id = model_config.id
            config_set = model_config.config_set
            config_name = model_config.config_name

        if log:
            print(f'Importing result from {config}')

        # TODO Add user and commit hashs
        model_run = query.create_model_run(
            model_config_id=model_config_id,
            polling_locations_set_id=polling_locations_set_id,
            username='',
            commit_hash='',
            created_at=current_time_utc(),
        )

        # Import each DF for this run
        edes_import_result = imports.import_edes(
            environment,
            config_set, config_name, model_run.id, df=demographic_ede, log=log,
        )
        results_import_result = imports.import_results(
            environment,
            config_set, config_name, model_run.id, df=result_df, log=log,
        )
        precinct_distances_import_result = imports.import_precinct_distances(
            environment,
            config_set, config_name, model_run.id, df=demographic_prec, log=log,
        )
        residence_distances_import_result = imports.import_residence_distances(
            environment,
            config_set, config_name, model_run.id, df=demographic_res, log=log,
        )

        current_run_results = [
            edes_import_result,
            results_import_result,
            precinct_distances_import_result,
            residence_distances_import_result,
        ]

        success = True

        # check for any problems and add the current_run_results to the overall results
        for current_run_result in current_run_results:
            success = success and current_run_result.success
            if log:
                print(current_run_result)

        model_run.success = success
        query.commit()

        if success and log:
            print(f'\nResults for config set {config_set}, config {config_name} successfuly written to db.')

        if not success:
            print(f'\nERROR: results for config set {config_set}, config {config_name} failed to write to db.')


def _compute_kp_alpha(df: pd.DataFrame):
    num = sum(x * y for x, y in zip(df[LOC_TOTAL_POPULATION], df[LOC_DISTANCE_M]))
    den = sum(x * y * y for x, y in zip(df[LOC_TOTAL_POPULATION], df[LOC_DISTANCE_M]))

    return num / den


def compute_kp_score(
    df: pd.DataFrame, beta: float,
    *,
    alpha: float=None,
    population_column_name: str=LOC_TOTAL_POPULATION,
    distance_column_name: str=LOC_DISTANCE_M
):
    distance_df = df[[population_column_name, distance_column_name]].copy()
    distance_df.columns = [LOC_TOTAL_POPULATION, LOC_DISTANCE_M]

    if beta == 0:
        return (df.population*df.distance_m).sum() / df.population.sum()

    alpha = _compute_kp_alpha(distance_df) if not alpha else alpha
    kappa = alpha * beta
    funky_sum = sum(x * math.exp(-kappa*y) for x, y in zip(df[LOC_TOTAL_POPULATION], df[LOC_DISTANCE_M]))
    tot_pop = distance_df.population.sum()

    return -math.log(funky_sum / tot_pop) / kappa
