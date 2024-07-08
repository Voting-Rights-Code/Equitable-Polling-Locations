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
# # Get YAML file input

config_path = 'York_SC_original_configs/York_config_original_2022.yaml'
os.path.isfile(config_path)
config = PollingModelConfig.load_config(config_path)
config_df = config.df()

# # Get Output Files

demographic_ede = pd.read_csv('York_SC_results/York_SC_original_configs.York_config_original_2022_edes.csv')
demographic_prec = pd.read_csv('York_SC_results/York_SC_original_configs.York_config_original_2022_precinct_distances.csv')
demographic_res = pd.read_csv('York_SC_results/York_SC_original_configs.York_config_original_2022_residence_distances.csv', dtype = {'id_orig':str})
result_df = pd.read_csv('York_SC_results/York_SC_original_configs.York_config_original_2022_result.csv', dtype = {'id_orig':str}, index_col = 0)

result_df = result_df.rename(columns = {"non-hispanic": "non_hispanic"})

write_results_bigquery(config, result_df, demographic_prec, demographic_res, demographic_ede, overwrite = True)
# client = bigquery.Client()
# project = "voting-rights-storage-test"
# dataset = "polling"
# out_type = "configs"
# project_dataset = project + "." + dataset
# table_id = project_dataset + "." + out_type
# job = client.load_table_from_dataframe(
#     config_df, 
#     table_id
# )
# job.result()  # Waits for the job to complete.




