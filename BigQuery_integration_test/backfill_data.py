from google.cloud import bigquery
from google.cloud import bigquery_storage
import pandas as pd
from ast import literal_eval # Converting CSV strings to lists
import arrow



# ==== Define parameters to change run-by-run ====

# ---- One-off runs ----
config_set = "York_SC_original_configs"
in_dir = config_set + "_collated"
overwrite = False

# ---- Big chunk of runs ----
filemaps = pd.read_csv('filemaps.csv')

# ==== Define function ====

def backfill_data(config_set, in_dir, overwrite = False):

    # ==== Construct a BigQuery client object ====
    client = bigquery.Client()

    # ==== Define parameters that should usually be fixed ====

    # Don't change this, it's the server-side name
    project = "voting-rights-storage-test"
    dataset = "polling"
    project_dataset = project + "." + dataset
    out_types= [
        "configs",
        "edes",
        "result",
        "precinct_distances",
        "residence_distances"
    ]


    # ==== Read files ====

    source_data = {} # Empty dict to store the data 
    for out_type in out_types:

        # ---- Define filepaths ----
        file_path = in_dir + "/" + config_set + "_" + out_type + ".csv"

        # ---- Read input files ---
        source_file = pd.read_csv(file_path)

        # ---- Clean input files ---
        # For config files (which are originally YAMLs), convert list columns and fix fussy timestamps
        list_cols = ['year', 'bad_types']
        if out_type == "configs":
               for col in list_cols:
                      source_file[col] = source_file[col].apply(lambda x: x.strip("[]").replace("'", "").split(", ") if x != '[]' else list())
               # Special case for year column - list of numerics, rather than list of strings
               source_file['year'] = source_file['year'].apply(lambda x: pd.to_numeric(x))
               source_file['run_time'] = source_file['run_time'].astype('datetime64[s]')

        source_data[out_type] = source_file


    # ==== Check existing data ====
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

    # ==== Check for existing data ====

    # --- If overwrite == False and a config with the given name exists, warning message ----
    if((existing_configs_yn == True) & (overwrite == False)):
        print(f"Config(s) [{configs_dup_str}] already exist; failing since overwrite == False")
        return

    # ---- If overwrite == True or no config exists ----
    # drop rows if necessary
    if((existing_configs_yn == True) & (overwrite == True)):
       for out_type in out_types:
            dml_statement = f'''
            DELETE FROM {dataset}.{out_type} WHERE config_name IN({configs_dup_str})
            '''
            job = client.query(dml_statement)
            # TODO: Running these jobs in serial right now, which is inefficient; need to monitor progress for all simultaneously
            # TODO: Check for error handling if these jobs fails
            job.result()
    
       print(f"Config(s) [{configs_dup_str}] already exist; dropping since overwrite == True")

    # ==== Write data ====

    for out_type in out_types:

        table_id = project_dataset + "." + out_type

        # ---- Upload ----
        job = client.load_table_from_dataframe(
            source_data[out_type], 
            table_id
        )

        # TO DO: Running these jobs in serial right now, which is inefficient; need to monitor progress for all simultaneously
        # TO DO: Drop new rows (revert) if not all tables update successfully
        job.result()  # Waits for the job to complete.

        table = client.get_table(table_id)  # Make an API request.
        print(
            "Loaded {} rows and {} columns to {}".format(
                table.num_rows, len(table.schema), table_id
            )
        )

    return

# ==== Run ====

backfill_data(config_set = config_set, in_dir = in_dir, overwrite = overwrite)

for i,j in zip(filemaps.config_set, filemaps.out_dir):
#   backfill_data(config_set = i, in_dir = j, overwrite = overwrite)
    print(f"Backfilled data for config set {i}")   