#######################################
#Created on 6 December 2023
#
#@author: Voting Rights Code
#@attribution: based off of code by Josh Murell
#######################################

import numpy as np
import pandas as pd
import os
import math
from utils import timer

from google.cloud import bigquery
from google.cloud import bigquery_storage
from google.api_core.exceptions import GoogleAPICallError
import arrow
import warnings

@timer
def incorporate_result(dist_df, model):
    '''Input: dist_df--the main data frame containing the data for model
              model -- the solved model
              model.matching -- pyo boolean variable for when a residence is matched to a precinct (res, prec):bool
    output: dataframe containing only the matched residences and precincts'''

    #turn matched solution into df
    matching_list= [(key[0], key[1], model.matching[key].value) for key in model.matching]
    matching_df = pd.DataFrame(matching_list, columns = ['id_orig', 'id_dest', 'matching'])

    #merge with dist_df
    result_df = pd.merge(dist_df, matching_df, on = ['id_orig', 'id_dest'])

    #keep only pairs that have been matched
    #if no matches, raise error
    if all(result_df['matching'].isnull()):
        raise ValueError('The model has no matched precincts')
    if any(result_df['matching'].isnull()):
        raise ValueError('The model has some unmatched precincts')
    result_df = result_df.loc[round(result_df['matching']).astype(int) ==1]
    return(result_df)

@timer
def demographic_domain_summary(result_df, domain):
    '''Input: result_df-- the distance an demographic population data for the matched residences and precincts
        domain-- ['id_dest', 'id_orig'] either the precinct of residence 
    Output: Calculate the average distances traveled by each demographic group that is assigned to each precinct or that lives in each residence.'''

    if domain not in ['id_dest', 'id_orig']:
        raise ValueError('domain much be in [id_dest, id_orig]')
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
    return demographic_prec

@timer
def demographic_summary(demographic_df, result_df, beta, alpha):
    '''Input: demographic_df-- the distance an demographic population data for the matched residences and precincts
    beta -- the inequality aversion factor
    alpha -- the data derived normalization factor
    Output: Calculate the average distances traveled by each demographic group.'''

    #calculate the total distance traveled by each demographic group
    demographic_dist = demographic_df['weighted_dist'].groupby('demographic').agg('sum')

    #calculate the total population of each demographic sent to each precinct
    demographic_population = demographic_df['demo_pop'].groupby('demographic').agg('sum')

    #merge the datasets
    demographic_summary = pd.concat([demographic_dist, demographic_population], axis = 1)

    #for base line comparison, or if config.beta ==0
    demographic_summary['avg_dist'] = demographic_summary['weighted_dist']/demographic_summary['demo_pop']

    if beta !=0: 
        
        #add the distance_m column back in from dist_df
        #1) first make demographics a column, not an index
        demographic_by_res = demographic_df.reset_index(['demographic'])
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
    return demographic_summary

@timer
def write_results_csv(result_folder, run_prefix, result_df, demographic_prec, demographic_res, demographic_ede):
    '''Write result, demographic_prec, demographic_res and demographic_ede to local CSV file'''

    #check if the directory exists
    if not os.path.exists(result_folder):
        os.makedirs(result_folder)
    result_file = f'{run_prefix}_result.csv'
    precinct_summary = f'{run_prefix}_precinct_distances.csv'
    residence_summary = f'{run_prefix}_residence_distances.csv'
    y_ede_summary = f'{run_prefix}_edes.csv'
    result_df.to_csv(os.path.join(result_folder, result_file), index = True)
    demographic_prec.to_csv(os.path.join(result_folder, precinct_summary), index = True)
    demographic_res.to_csv(os.path.join(result_folder, residence_summary), index = True)
    demographic_ede.to_csv(os.path.join(result_folder, y_ede_summary), index = True)

    return


def write_results_bigquery(config, result_df, demographic_prec, demographic_res, demographic_ede, overwrite = False, log = True):
    '''Write result, demographic_prec, demographic_res and demographic_ede to BigQuery SQL tables'''

    # ==== Construct a BigQuery client object ====
    client = bigquery.Client()


    # ==== Define parameters that should usually be fixed ====

    # Don't change this, it's the server-side name
    project = "voting-rights-storage-test"
    dataset = "polling"
    project_dataset = project + "." + dataset


    # ==== Create dict of outputs and related name ====
    config_df = config.df()

    # Convert indices to columns
    demographic_ede = demographic_ede.reset_index()
    demographic_res = demographic_res.reset_index()

    # TEMPORARY: Fix type issues
    # TODO: change these at the source
    #demographic_res['id_orig'] = demographic_res['id_orig'].astype('string')
    result_df['id_orig'] = result_df['id_orig'].astype('string')
    demographic_res['id_orig'] = demographic_res['id_orig'].astype('string')

    source_data = {
        "configs": config_df,
        "edes": demographic_ede,
        "result": result_df,
        "precinct_distances": demographic_prec,
        "residence_distances": demographic_res
    } 
    out_types = source_data.keys()

    # Cycle over out_types other than config_df, and append config_name and config_set columns to them
    for out_type in out_types:
        if(out_type != "configs"):
            source_data[out_type]['config_name'] = config.config_name
            source_data[out_type]['config_set'] = config.config_set

    # Drop unused 'county' field from results
    # TODO: never create this field (we instead handle country by joining with the configs table)
    source_data['result'] = source_data['result'].drop('county', axis = 1)


    # ==== Handle duplicated data ====
    # ---- TO DO: Check types of output before writing, possibly using the existing type data from the table_specs.py file ----
    # ---- TO DO: Check primary key uniqueness for tables

    # ---- Check whether any of the configs already exist ----
    configs_series = "'" + source_data['configs']['config_name'] + "'"
    configs_str = configs_series.str.cat(sep = ",")

    query = f'''
    SELECT config_name
    FROM {dataset}.configs 
    WHERE config_name IN({configs_str})
    '''

    existing_configs_df = client.query(query).to_dataframe()
    existing_configs_yn = existing_configs_df.shape[0] > 0

    configs_dup_series = "'" + existing_configs_df['config_name'] + "'"
    configs_dup_str = configs_dup_series.str.cat(sep = ", ")

    # --- If overwrite == False and a config with the given name exists, warning message ----
    if((existing_configs_yn == True) & (overwrite == False)):
        warnings.warn(f"Config(s) [{configs_dup_str}] already exist; failing since overwrite == False")
        return

    # ---- If overwrite == True or no config exists, drop existing rows ----
    # drop rows if necessary
    if((existing_configs_yn == True) & (overwrite == True)):
       for out_type in out_types:
            dml_statement = f'''
            DELETE FROM {dataset}.{out_type} WHERE config_name IN({configs_dup_str})
            '''
            job = client.query(dml_statement)
            job.result()
    
       warnings.warn(f"Config(s) [{configs_dup_str}] already exist; dropping since overwrite == True")


    # ==== Write data ====
    write_success = {}
    for out_type in out_types:

        table_id = project_dataset + "." + out_type

        # ---- Upload ----
        # Try uploading
        try:
            job = client.load_table_from_dataframe(
                source_data[out_type], 
                table_id
            )

            # TO DO: Running these jobs in serial right now, which is inefficient; need to monitor progress for all simultaneously
            # TO DO: Drop new rows (revert) if not all tables update successfully
            job.result()  # Waits for the job to complete.

            if(log == True):
                print(
                    "Wrote {} rows to table {}".format(
                        job.output_rows, table_id
                    )
                )

            write_success[out_type] = True

        except GoogleAPICallError:
            warnings.warn(f'Failed to write table {table_id}')
            write_success[out_type] = False
            break

    ## ==== Delete data if any writing failed ====
    if False in write_success.values():
            for out_type in write_success.keys():
                if( write_success[out_type] == True):
                    dml_statement = f'''
                    DELETE FROM {dataset}.{out_type} WHERE config_name IN({configs_str})
                    '''
                    job = client.query(dml_statement)
                    job.result()

                    if(log == True): print(f'''
                    Deleted rows from table {dataset}.{out_type} with config name(s) [{configs_str}] because of write failures to other tables
                    ''')


    return



