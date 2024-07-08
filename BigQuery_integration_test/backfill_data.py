from google.cloud import bigquery
from google.cloud import bigquery_storage
import pandas as pd
from ast import literal_eval # Converting CSV strings to lists
import arrow



# ==== Define parameters to change run-by-run ====
overwrite = True
check_dups = True


# ---- One-off runs ----
config_set = "York_SC_original_configs"
in_dir = config_set + "_collated"

# ---- Big chunk of runs ----
filemaps = pd.read_csv('filemaps.csv')


# ==== Construct a BigQuery client object and define configs ====
client = bigquery.Client()

job_configs = {
    "configs": bigquery.LoadJobConfig(
        schema=[
           bigquery.SchemaField("config_name", bigquery.enums.SqlTypeNames.STRING, "REQUIRED"),
           bigquery.SchemaField("location", bigquery.enums.SqlTypeNames.STRING, "REQUIRED"),
           bigquery.SchemaField("config_set", bigquery.enums.SqlTypeNames.STRING, "REQUIRED"),
           bigquery.SchemaField("year", bigquery.enums.SqlTypeNames.STRING, "REPEATED"),
           bigquery.SchemaField("bad_types", bigquery.enums.SqlTypeNames.STRING, "REPEATED"),
           bigquery.SchemaField("beta", bigquery.enums.SqlTypeNames.FLOAT, "REQUIRED"),
           bigquery.SchemaField("time_limit", bigquery.enums.SqlTypeNames.FLOAT, "REQUIRED"),
           bigquery.SchemaField("capacity", bigquery.enums.SqlTypeNames.FLOAT, "REQUIRED"),
           bigquery.SchemaField("precincts_open", bigquery.enums.SqlTypeNames.INTEGER, "NULLABLE"),
           bigquery.SchemaField("max_min_mult", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
           bigquery.SchemaField("maxpctnew", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
           bigquery.SchemaField("minpctold", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
           bigquery.SchemaField("commit_hash", bigquery.enums.SqlTypeNames.STRING, "NULLABLE"),
           bigquery.SchemaField("run_time", bigquery.enums.SqlTypeNames.TIMESTAMP, "NULLABLE")
        ],
        clustering_fields = ['config_set', 'config_name']
    ),
    "edes": bigquery.LoadJobConfig(
        schema=[
               bigquery.SchemaField("demographic", bigquery.enums.SqlTypeNames.STRING, "REQUIRED"),
               bigquery.SchemaField("weighted_dist", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
               bigquery.SchemaField("avg_dist", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
               bigquery.SchemaField("demo_res_obj_summand", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
               bigquery.SchemaField("demo_pop", bigquery.enums.SqlTypeNames.INTEGER, "NULLABLE"),
               bigquery.SchemaField("avg_KP_weight", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
               bigquery.SchemaField("y_EDE", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
               bigquery.SchemaField("config_name", bigquery.enums.SqlTypeNames.STRING, "REQUIRED"),
               bigquery.SchemaField("config_set", bigquery.enums.SqlTypeNames.STRING, "REQUIRED")
            ],
        clustering_fields = ['config_set', 'config_name']
    ),
    "result": bigquery.LoadJobConfig(
        schema=[
           bigquery.SchemaField("id_orig", bigquery.enums.SqlTypeNames.STRING, "REQUIRED"),
           bigquery.SchemaField("id_dest", bigquery.enums.SqlTypeNames.STRING, "REQUIRED"),
           bigquery.SchemaField("distance_m", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
           bigquery.SchemaField("address", bigquery.enums.SqlTypeNames.STRING, "NULLABLE"),
           bigquery.SchemaField("dest_lat", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
           bigquery.SchemaField("dest_lon", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
           bigquery.SchemaField("orig_lat", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
           bigquery.SchemaField("orig_lon", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
           bigquery.SchemaField("location_type", bigquery.enums.SqlTypeNames.STRING, "NULLABLE"),
           bigquery.SchemaField("dest_type", bigquery.enums.SqlTypeNames.STRING, "NULLABLE"),
           bigquery.SchemaField("population", bigquery.enums.SqlTypeNames.INTEGER, "NULLABLE"),
           bigquery.SchemaField("hispanic", bigquery.enums.SqlTypeNames.INTEGER, "NULLABLE"),
           bigquery.SchemaField("non_hispanic", bigquery.enums.SqlTypeNames.INTEGER, "NULLABLE"),
           bigquery.SchemaField("white", bigquery.enums.SqlTypeNames.INTEGER, "NULLABLE"),
           bigquery.SchemaField("black", bigquery.enums.SqlTypeNames.INTEGER, "NULLABLE"),
           bigquery.SchemaField("asian", bigquery.enums.SqlTypeNames.INTEGER, "NULLABLE"),
           bigquery.SchemaField("pacific_islander", bigquery.enums.SqlTypeNames.INTEGER, "NULLABLE"),
           bigquery.SchemaField("other", bigquery.enums.SqlTypeNames.INTEGER, "NULLABLE"),
           bigquery.SchemaField("multiple_races", bigquery.enums.SqlTypeNames.INTEGER, "NULLABLE"),
           bigquery.SchemaField("other", bigquery.enums.SqlTypeNames.INTEGER, "NULLABLE"),
           bigquery.SchemaField("Weighted_dist", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
           bigquery.SchemaField("KP_factor", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
           bigquery.SchemaField("new_location", bigquery.enums.SqlTypeNames.INTEGER, "NULLABLE"),
           bigquery.SchemaField("matching", bigquery.enums.SqlTypeNames.INTEGER, "NULLABLE"),
           bigquery.SchemaField("config_name", bigquery.enums.SqlTypeNames.STRING, "REQUIRED"),
           bigquery.SchemaField("config_set", bigquery.enums.SqlTypeNames.STRING, "REQUIRED")
        ],
        clustering_fields = ['config_set', 'config_name']
    ),
    "precinct_distances": bigquery.LoadJobConfig(
        schema=[
           bigquery.SchemaField("id_dest", bigquery.enums.SqlTypeNames.STRING, "REQUIRED"),
           bigquery.SchemaField("demographic", bigquery.enums.SqlTypeNames.STRING, "NULLABLE"),
           bigquery.SchemaField("demo_pop", bigquery.enums.SqlTypeNames.INTEGER, "NULLABLE"),
           bigquery.SchemaField("avg_dist", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
           bigquery.SchemaField("config_name", bigquery.enums.SqlTypeNames.STRING, "REQUIRED"),
           bigquery.SchemaField("config_set", bigquery.enums.SqlTypeNames.STRING, "REQUIRED")
        ],
        clustering_fields = ['config_set', 'config_name']
    ),
    "residence_distances": bigquery.LoadJobConfig(
        schema=[
           bigquery.SchemaField("id_orig", bigquery.enums.SqlTypeNames.STRING, "REQUIRED"),
           bigquery.SchemaField("demographic", bigquery.enums.SqlTypeNames.STRING, "NULLABLE"),
           bigquery.SchemaField("weighted_dist", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
           bigquery.SchemaField("demo_pop", bigquery.enums.SqlTypeNames.INTEGER, "NULLABLE"),
           bigquery.SchemaField("avg_dist", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
           bigquery.SchemaField("config_name", bigquery.enums.SqlTypeNames.STRING, "REQUIRED"),
           bigquery.SchemaField("config_set", bigquery.enums.SqlTypeNames.STRING, "REQUIRED")
        ],
        clustering_fields = ['config_set', 'config_name']
    )
}


# ==== Define function ====

def backfill_data(config_set, in_dir, overwrite = False):

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
               source_file['run_time'] = source_file['run_time'].astype('datetime64[s]')
        if ((out_type == "result" ) | (out_type == "residence_distances")):
            source_file['id_orig'] = source_file['id_orig'].astype(str)

        source_data[out_type] = source_file


    # ==== Check existing data ====
    # ---- TO DO: Check types of output before writing, possibly using the existing type data from the table_specs.py file ----
    # ---- TO DO: Check primary key uniqueness for tables

    # ---- Check whether any of the configs already exist ----
    if(check_dups == True):
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
            table_id,
            job_config = job_configs[out_type]
        )

        # TO DO: Running these jobs in serial right now, which is inefficient; need to monitor progress for all simultaneously
        # TO DO: Drop new rows (revert) if not all tables update successfully
        job.result()  # Waits for the job to complete.

        # TO DO: Change potentially-misleading message below; fetch the number of *new* rows via a select statement
        table = client.get_table(table_id)  # Make an API request.
        print(
            "Loaded {} rows and {} columns to {}".format(
                table.num_rows, len(table.schema), table_id
            )
        )

    return

# ==== Run ====

backfill_data(config_set = config_set, in_dir = in_dir, overwrite = overwrite)

# for i,j in zip(filemaps.config_set, filemaps.out_dir):
#     backfill_data(config_set = i, in_dir = j, overwrite = overwrite)
#     print(f"Backfilled data for config set {i}")   