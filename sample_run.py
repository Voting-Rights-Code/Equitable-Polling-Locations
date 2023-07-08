import math
import numpy as np
import pandas as pd
import pyomo.environ as pyo
import test_config_refactor as config
from data_for_model import (clean_data, alpha_all)
from model_factory import polling_model_factory
from model_solver import solve_model

#get main data frame
dist_df = clean_data(config.location, config.level, config.year)

#get alpha
alpha_df = clean_data(config.location, 'original', config.year)
    # TODO: (CR) I don't like having to call this twice like this. Need a better method
alpha  = alpha_all(alpha_df)

#build model
ea_model = polling_model_factory(dist_df, alpha, config)
print(f'model built. Solve for {config.time_limit} seconds')

#solve model
result = solve_model(ea_model, config.time_limit)


####organize results#####

#turn matched solution into df
matching_list= [(key[0], key[1], ea_model.matching[key].value) for key in ea_model.matching]
matching_df = pd.DataFrame(matching_list, columns = ['id_orig', 'id_dest', 'matching'])

#merge with dist_df
result_df = pd.merge(dist_df, matching_df, on = ['id_orig', 'id_dest'])


#keep only pairs that have been matched
if all(result_df['matching'].isnull()):
    #fake some data
    #TODO: fake data for test puroses only. need sample data that can
    #be made into a feasible solutions
    residences = list(set(result_df.id_orig))
    to_one = residences[0:3] #assign these to precincts[0]
    to_two = residences[3:8] #assign these to precincts[1]
    to_three = residences[8:10] #assign these to precincts[2]
    precincts = list(set(result_df.id_dest))
    result_df.matching = 0
    result_df.loc[(result_df.id_orig.isin(to_one)) & (result_df. id_dest == precincts[0]), 'matching'] = 1 
    result_df.loc[(result_df.id_orig.isin(to_two)) & (result_df.id_dest == precincts[1]), 'matching'] = 1
    result_df.loc[(result_df.id_orig.isin(to_three)) & (result_df.id_dest == precincts[2]), 'matching'] = 1
result_df = result_df.loc[result_df['matching'] ==1]

#get the population/ demographics at each precinct
precinct_population = result_df[['id_dest', 'population','white', 'black', 'native', 'asian', 'hispanic', 'poverty_0_50', 'poverty_50_99']].groupby('id_dest').agg('sum')

#get the average weighted distances to precinct for each population groups
#NOTE: for F's sake, this is why i hate pandas
prec_res_weighted_dist = result_df[['population','white', 'black', 'native', 'asian', 'hispanic', 'poverty_0_50', 'poverty_50_99']].multiply(result_df.distance_m, axis = 'index')
prec_res_weighted_dist.insert(0, "id_dest", result_df.id_dest)
precinct_total_dist = prec_res_weighted_dist.groupby('id_dest').agg('sum')

breakpoint()
precinct_avg_dist = pd.DataFrame({'id_dest': precincts}).set_index('id_dest')
for col in precinct_total_dist.columns:
    precinct_avg_dist[col] = precinct_total_dist[col]/precinct_population[col]

#get the y_EDEs for the different demographic groups
#NOTE: for now, if beta= 0, returning the weighted averge
#THIS IS NOT WHAT IS IN THE ORIGINAL CODE

demographic_res_dist = pd.melt(result_df[['id_orig', 'distance_m', 'population','white', 'black', 'native', 'asian', 'hispanic', 'poverty_0_50', 'poverty_50_99']], id_vars = ['id_orig', 'distance_m'], value_vars = ['population','white', 'black', 'native', 'asian', 'hispanic', 'poverty_0_50', 'poverty_50_99'], var_name = 'demographic', value_name = 'demo_pop')

demographic_res_dist['weighted_dist'] = demographic_res_dist['demo_pop']*demographic_res_dist['distance_m']

demographic_dist = demographic_res_dist[['demographic', 'weighted_dist']].groupby('demographic').agg('sum')

demographic_population = demographic_res_dist[['demographic', 'demo_pop']].groupby('demographic').agg('sum')

#for base line comparison, or if config.beta ==0
demographic_dist['avg_dist'] = demographic_dist['weighted_dist']/demographic_population['demo_pop']

#if config.beta !=0:
demographic_res_dist['KP_factor'] =  math.e**(-config.beta*alpha*demographic_res_dist['distance_m'])
demographic_res_dist['demo_res_obj_summand'] = demographic_res_dist['demo_pop']*demographic_res_dist['KP_factor']

demographic_ede = demographic_res_dist[['demographic', 'demo_res_obj_summand', 'demo_pop']].groupby('demographic').agg('sum')
demographic_ede['avg_KP_weight'] =  demographic_ede.demo_res_obj_summand/demographic_ede.demo_pop
demographic_ede['y_EDE'] = (-1/(config.beta * alpha))*np.log(demographic_ede['avg_KP_weight'])


