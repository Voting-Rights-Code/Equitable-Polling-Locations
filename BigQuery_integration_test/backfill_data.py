from google.cloud import bigquery
import pandas as pd
from ast import literal_eval
import arrow

# Construct a BigQuery client object.
client = bigquery.Client()

# ==== Define parameters to change run-by-run ====

config_set = "York_SC_original_configs"
in_dir = config_set + "_collated"

# ==== Define parameters that should usually be fixed ====

# Don't change this, it's the server-side name
project_dataset = "voting-rights-storage-test.polling"
out_types= [
    "configs",
    "edes",
    "result",
    "precinct_distances",
    "residence_distances"
]

# TODO: Check whether a given run name already exists


# ==== Loop over files ====

for out_type in out_types:

    # ---- Define filepaths ----
    table_id = project_dataset + "." + out_type
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


    # ---- Upload ----
    job = client.load_table_from_dataframe(
        source_file, 
        table_id
    )

    # TODO: Running these jobs in serial right now, which is inefficient; need to montior progress for all simultaneously
    # TODO: Drop new rows (revert) if not all tables update successfully
    job.result()  # Waits for the job to complete.

    table = client.get_table(table_id)  # Make an API request.
    print(
        "Loaded {} rows and {} columns to {}".format(
            table.num_rows, len(table.schema), table_id
        )
    )