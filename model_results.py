#######################################
#Created on 6 December 2023
#
#@author: Voting Rights Code
#@attribution: based off of code by Josh Murell
#######################################

import math
import os
import threading

import numpy as np
import pandas as pd

import db
import db_import_cli
from model_config import PollingModelConfig
from utils import timer, current_time_utc

lock = threading.Lock()

@timer
def incorporate_result(dist_df, model):
    '''Input: dist_df--the main data frame containing the data for model
              model -- the solved model
              model.matching -- pyo boolean variable for when a residence is matched to a precinct (res, prec):bool
    output: dataframe containing only the matched residences and precincts'''

    #turn matched solution into df
    matching_list= [(key[0], key[1], model.matching[key].value) for key in model.matching]
    matching_df = pd.DataFrame(matching_list, columns = ['id_orig', 'id_dest', 'matching'])
    #the matching doesn't always give an integer value. Replace the value with the integer it would round to   
    matching_df['matching'].mask(matching_df['matching']>=0.5, 1, inplace=True)
    matching_df['matching'].mask(matching_df['matching']<0.5, 0, inplace=True)

    #merge with dist_df
    result_df = pd.merge(dist_df, matching_df, on = ['id_orig', 'id_dest'])

    #keep only pairs that have been matched
    #if no matches, raise error
    if all(result_df['matching'].isnull()):
        raise ValueError('The model has no matched precincts')
    if any(result_df['matching'].isnull()):
        raise ValueError('The model has some unmatched precincts')
    result_df = result_df.loc[result_df['matching'] ==1]
    
    return result_df

@timer
def demographic_domain_summary(result_df, domain):
    '''Input: result_df-- the distance an demographic population data for the matched residences and precincts
        domain-- ['id_dest', 'id_orig'] either the precinct of residence
    Output: Calculate the average distances traveled by each demographic group that is assigned to each precinct or that lives in each residence.'''

    if domain not in ['id_dest', 'id_orig']:
        raise ValueError('domain much be in [id_dest, id_orig]')
    #extract unique source value for later
    source_value = result_df['source'].unique()
    #Transform to get distance and population by demographic, destination pairs for each origin
    demographic_all = pd.melt(result_df[[domain, 'distance_m', 'population','white', 'black', 'native', 'asian', 'hispanic']], id_vars = [domain, 'distance_m'], value_vars = ['population','white', 'black', 'native', 'asian', 'hispanic'], var_name = 'demographic', value_name = 'demo_pop')

    #create a weighted distance column for people of each demographic
    demographic_all['weighted_dist'] = demographic_all['demo_pop']*demographic_all['distance_m']

    #calculate the total population of each demographic sent to each precinct
    demographic_pop = demographic_all[[domain, 'demographic', 'demo_pop']].groupby([domain, 'demographic']).agg('sum')

    #calculate the total distance traveled by each demographic group
    demographic_dist = demographic_all[[domain, 'demographic', 'weighted_dist']].groupby([domain, 'demographic']).agg('sum')

    #merge the demographic_pop and demographic_dist
    demographic_prec = pd.concat([demographic_dist, demographic_pop], axis = 1)

    #calculate the average distance
    demographic_prec['avg_dist'] =  demographic_prec['weighted_dist']/ demographic_prec['demo_pop']

    #add source data back in
    demographic_prec['source'] = source_value[0]
    #reset index for reading into r
    demographic_prec = demographic_prec.reset_index()

    return demographic_prec

@timer
def demographic_summary(demographic_df, result_df, beta, alpha):
    '''Input: demographic_df-- the distance an demographic population data for the matched residences and precincts
    beta -- the inequality aversion factor
    alpha -- the data derived normalization factor
    Output: Calculate the average distances traveled by each demographic group.'''

    #extract unique source value for later
    source_value = result_df['source'].unique()

    #calculate the total distance traveled by each demographic group
    demographic_dist = demographic_df[['demographic', 'weighted_dist']].groupby('demographic').agg('sum')

    #calculate the total population of each demographic sent to each precinct
    demographic_population = demographic_df[['demographic','demo_pop']].groupby('demographic').agg('sum')

    #merge the datasets
    demographic_summary = pd.concat([demographic_dist, demographic_population], axis = 1)

    #for base line comparison, or if config.beta ==0
    demographic_summary['avg_dist'] = demographic_summary['weighted_dist']/demographic_summary['demo_pop']

    if beta !=0:

        #add the distance_m column back in from dist_df
        #1) set index of demographic_df to 'id_orig'
        demographic_by_res = demographic_df.set_index('id_orig')
        #2) set index for results to 'id_orig'
        distances = result_df[['id_orig', 'distance_m']].set_index('id_orig')
        #3) merge on id_orig (index for both)
        demographics = demographic_by_res.merge(distances, left_index = True, right_index = True, how = 'outer')

        #add in a KP factor column
        demographics['KP_factor'] =  math.e**(-beta*alpha*demographics['distance_m'])
        #calculate the summand for the objective function
        demographics['demo_res_obj_summand'] = demographics['demo_pop']*demographics['KP_factor']

        #compute the ede for each demographic group
        demographic_ede = demographics[['demographic','demo_res_obj_summand', 'demo_pop']].groupby('demographic').agg('sum')
        demographic_ede['avg_KP_weight'] =  demographic_ede.demo_res_obj_summand/demographic_ede.demo_pop
        demographic_ede['y_EDE'] = (-1/(beta * alpha))*np.log(demographic_ede['avg_KP_weight'])

        #merge the datasets
        demographic_summary = pd.concat([demographic_summary[['weighted_dist', 'avg_dist']], demographic_ede], axis = 1)

        #add source data back in
        demographic_summary['source'] = source_value[0]

        #reset index for reading into r
        demographic_summary = demographic_summary.reset_index()


    return demographic_summary

@timer
def write_results_csv(
    result_folder: str,
    run_prefix: str,
    result_df: pd.DataFrame,
    demographic_prec: pd.DataFrame,
    demographic_res: pd.DataFrame,
    demographic_ede: pd.DataFrame,
):
    '''Write result, demographic_prec, demographic_res and demographic_ede to local CSV file'''

    #check if the directory exists
    if not os.path.exists(result_folder):
        os.makedirs(result_folder)
    result_file = f'{run_prefix}_results.csv'
    precinct_summary = f'{run_prefix}_precinct_distances.csv'
    residence_summary = f'{run_prefix}_residence_distances.csv'
    y_ede_summary = f'{run_prefix}_edes.csv'



    try:
        result_df.to_csv(os.path.join(result_folder, result_file), index = True)
        demographic_prec.to_csv(os.path.join(result_folder, precinct_summary), index = True)
        demographic_res.to_csv(os.path.join(result_folder, residence_summary), index = True)
        demographic_ede.to_csv(os.path.join(result_folder, y_ede_summary), index = True)
    except FileExistsError:
        print(f'Output file already exists for {result_folder}/{run_prefix}, set replace = True to overwrite')


@timer
def write_results_bigquery(
    source_config: PollingModelConfig,
    result_df: pd.DataFrame,
    demographic_prec: pd.DataFrame,
    demographic_res: pd.DataFrame,
    demographic_ede: pd.DataFrame,
    log: bool = False,
):
    '''Write result, demographic_prec, demographic_res and demographic_ede to BigQuery SQL tables'''

    # Setup a thread lock so that only one write to bigquery happens at a time.
    # This is to prevent problems with tqdm being used in model_run_cli.py
    with lock:
        (model_config, _) = db_import_cli.import_model_config(source_config)
        model_config = db.find_or_create_model_config(model_config)
        if log:
            print(f'Importing result from {model_config}')

        # TODO Add user and commit hash
        model_run = db.create_model_run(model_config.id, '', '', current_time_utc())

        config_set = model_config.config_set
        config_name = model_config.config_name

        # Import each DF for this run
        edes_import_result = db_import_cli.import_edes(
            config_set, config_name, model_run.id, df=demographic_ede, log=log,
        )
        results_import_result = db_import_cli.import_results(
            config_set, config_name, model_run.id, df=result_df, log=log,
        )
        precinct_distances_import_result = db_import_cli.import_precinct_distances(
            config_set, config_name, model_run.id, df=demographic_prec, log=log,
        )
        residence_distances_import_result = db_import_cli.import_residence_distances(
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
        db.commit()

        if success and log:
            print(f'\nResults for config set {config_set}, config {config_name} successfuly written to db.')


def _compute_kp_alpha(df):
    num = sum(x*y for x, y in zip(df['population'], df['distance_m']))
    den = sum(x*y*y for x, y in zip(df['population'], df['distance_m']))
    return num/den

def compute_kp_score(df, beta, *, alpha=None, population_column_name='population', distance_column_name='distance_m'):
    distance_df = df[[population_column_name, distance_column_name]].copy()
    distance_df.columns = ['population', 'distance_m']
    if beta == 0:
        return (df.population*df.distance_m).sum()/df.population.sum()
    alpha = _compute_kp_alpha(distance_df) if not alpha else alpha
    kappa = alpha * beta
    funky_sum = sum(x * math.exp(-kappa*y) for x, y in zip(df['population'], df['distance_m']))
    tot_pop = distance_df.population.sum()
    return -math.log(funky_sum/tot_pop)/kappa
