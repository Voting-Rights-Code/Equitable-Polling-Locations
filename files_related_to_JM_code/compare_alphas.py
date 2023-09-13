from test_config_refactor import * #For testing only. Remove later 
import time
import data_for_model as data_sa
import get_data as data_jm
import pyomo.environ as pyo
from pyomo.opt import SolverStatus, TerminationCondition
import pandas as pd

####################
#Get Josh's alpha value
####################
city_to_file = {'Atlanta': 'atlanta.csv',
                'Cincinnati': 'cincinnati.csv',
                'Richmond': 'richmond.csv',
                'Salem': 'salem.csv',
                'Test':'salem_sample.csv',
                'Dallas': 'dallas.csv'}
dist = city_to_file[location]
basedist = data_jm.get_basedist(dist, location, year)
dist_df = data_jm.get_dist_df(dist, location, level, year)
alpha_df = data_jm.get_dist_df(dist, location, 'original', year)
MAX_MIN_DIST = 1.2*data_jm.get_max_min_dist(basedist)

#Josh's function on the two dfs
#alpha_jm_basedist = data_jm.alpha_def(MAX_MIN_DIST, basedist)
alpha_jm_dist_df = data_jm.alpha_def(MAX_MIN_DIST, dist_df)
alpha_jm_alpha_df = data_jm.alpha_def(MAX_MIN_DIST, alpha_df)


####################
#Get Susama's alpha values
####################
#all data for a location, year
basedist = data_sa.get_base_dist(location, year)
#only the data for a location year at the desire level
dist_df = data_sa.get_dist_df(basedist, level, year)
#only the data for a location year at the desire level with original polls
alpha_df = data_sa.get_dist_df(dist_df,'original', year)

#Susama's functions on the two dfs 

#rewrite of Josh's functions
alpha_all_basedist = data_sa.alpha_all(basedist)
alpha_all_dist_df = data_sa.alpha_all(dist_df)
alpha_all_alpha_df = data_sa.alpha_all(alpha_df)
#alpha taking only the min distances
alpha_min_basedist = data_sa.alpha_min(basedist)
alpha_min_dist_df = data_sa.alpha_min(dist_df)
alpha_min_alpha_df = data_sa.alpha_min(alpha_df)
#alpha taking only the mean distances
alpha_mean_basedist = data_sa.alpha_mean(basedist)
alpha_mean_dist_df = data_sa.alpha_mean(dist_df)
alpha_mean_alpha_df = data_sa.alpha_mean(alpha_df)

#########################
#Write to dictionary
#########################

alpha_dict = {#'alpha_jm_b': alpha_jm_basedist,
              'alpha_jm_d': alpha_jm_dist_df, 
              'alpha_jm_a': alpha_jm_alpha_df,
              #'alpha_all_b': alpha_all_basedist,
              'alpha_all_d':alpha_all_dist_df,
              'alpha_all_a':alpha_all_alpha_df,
              #'alpha_min_b': alpha_min_basedist,
              'alpha_min_d': alpha_min_dist_df,
              'alpha_min_a':alpha_min_alpha_df,
              #'alpha_mean_b': alpha_mean_basedist,
              'alpha_mean_d': alpha_mean_dist_df,
              'alpha_mean_a':alpha_mean_alpha_df,
}
print(alpha_dict)