from typing import List
from dataclasses import dataclass
import yaml
import pandas as pd

import os
import datetime as dt

from google.cloud import bigquery
from google.cloud import bigquery_storage
import arrow

from model_config import PollingModelConfig
from model_results import write_results_bigquery

import pickle
# # Get YAML file input

#config_path = 'York_SC_original_configs/York_config_original_2022.yaml'
config_path = 'Chatham_County_GA_results/Chatham_config_original_2020.yaml'
os.path.isfile(config_path)
config = PollingModelConfig.load_config(config_path)
config_df = config.df()

# # Get Output Files
with open('Chatham_County_GA_results/Chatham_County_GA_original_configs.Chatham_config_original_2020_edes.pkl', 'rb') as file:
	demographic_ede = pickle.load(file)
with open('Chatham_County_GA_results/Chatham_County_GA_original_configs.Chatham_config_original_2020_precinct_distances.pkl', 'rb') as file:
	demographic_prec = pickle.load(file)
with open('Chatham_County_GA_results/Chatham_County_GA_original_configs.Chatham_config_original_2020_residence_distances.pkl', 'rb') as file:
	demographic_res = pickle.load(file)
with open('Chatham_County_GA_results/Chatham_County_GA_original_configs.Chatham_config_original_2020_result.pkl', 'rb') as file:
	result_df = pickle.load(file)

#demographic_ede = pd.read_csv('York_SC_results/York_SC_original_configs.York_config_original_2022_edes.csv')
#demographic_prec = pd.read_csv('York_SC_results/York_SC_original_configs.York_config_original_2022_precinct_distances.csv')
#demographic_res = pd.read_csv('York_SC_results/York_SC_original_configs.York_config_original_2022_residence_distances.csv')
#result_df = pd.read_csv('York_SC_results/York_SC_original_configs.York_config_original_2022_result.csv', index_col = 0)

#result_df = result_df.rename(columns = {"non-hispanic": "non_hispanic"})

write_results_bigquery(config, result_df, demographic_prec, demographic_res, demographic_ede, overwrite = True)
