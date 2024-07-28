from google.cloud import bigquery
from google.cloud import bigquery_storage
import pandas as pd
from ast import literal_eval # Converting CSV strings to lists
import arrow

from model_results import write_results_bigquery

# ==== Define parameters to change run-by-run ====
overwrite = True

# ---- One-off runs ----
config_set = "York_SC_original_configs"
in_dir = "BigQuery_integration/" + config_set + "_collated"

# ---- Big chunk of runs ----
filemaps = pd.read_csv('BigQuery_integration/filemaps_root.csv')


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


    write_results_bigquery(
        config = source_data['configs'],
        result_df = source_data['result'],
        demographic_prec = source_data['precinct_distances'],
        demographic_res = source_data['residence_distances'],
        demographic_ede = source_data['edes'],
        overwrite = overwrite,
        csv_backfill = True
    )


    return

# ==== Run ====

# Test with one config
#backfill_data(config_set = config_set, in_dir = in_dir, overwrite = overwrite)

# Backfill all configs
for i,j in zip(filemaps.config_set, filemaps.out_dir):
    print(f"Backfilling data for config set {i}")   
    backfill_data(config_set = i, in_dir = j, overwrite = overwrite)
