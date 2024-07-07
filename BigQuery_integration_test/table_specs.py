from google.cloud import bigquery

# Construct a BigQuery client object.
client = bigquery.Client()

# ==== Define configs ====

job_configs = {
    "configs": bigquery.LoadJobConfig(
        schema=[
           bigquery.SchemaField("config_name", bigquery.enums.SqlTypeNames.STRING, "REQUIRED"),
           bigquery.SchemaField("location", bigquery.enums.SqlTypeNames.STRING, "REQUIRED"),
           bigquery.SchemaField("config_set", bigquery.enums.SqlTypeNames.STRING, "REQUIRED"),
           bigquery.SchemaField("year", bigquery.enums.SqlTypeNames.INTEGER, "REPEATED"),
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
               bigquery.SchemaField("config_set", bigquery.enums.SqlTypeNames.STRING, "REQUIRED"),
            ],
        clustering_fields = ['config_set', 'config_name']
    ),
    "result": bigquery.LoadJobConfig(
        schema=[
           bigquery.SchemaField("id_orig", bigquery.enums.SqlTypeNames.INTEGER, "REQUIRED"),
           bigquery.SchemaField("id_dest", bigquery.enums.SqlTypeNames.STRING, "REQUIRED"),
           bigquery.SchemaField("distance_m", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
           bigquery.SchemaField("address", bigquery.enums.SqlTypeNames.STRING, "NULLABLE"),
           bigquery.SchemaField("dest_lat", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
           bigquery.SchemaField("dest_lon", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
           bigquery.SchemaField("orig_lat", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
           bigquery.SchemaField("orin_lon", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
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
           bigquery.SchemaField("avg_dist", bigquery.enums.SqlTypeNames.INTEGER, "NULLABLE"),
           bigquery.SchemaField("config_name", bigquery.enums.SqlTypeNames.STRING, "REQUIRED"),
           bigquery.SchemaField("config_set", bigquery.enums.SqlTypeNames.STRING, "REQUIRED"),
        ],
        clustering_fields = ['config_set', 'config_name']
    ),
    "residence_distances": bigquery.LoadJobConfig(
        schema=[
           bigquery.SchemaField("id_orig", bigquery.enums.SqlTypeNames.INTEGER, "REQUIRED"),
           bigquery.SchemaField("demographic", bigquery.enums.SqlTypeNames.STRING, "NULLABLE"),
           bigquery.SchemaField("weighted_dist", bigquery.enums.SqlTypeNames.FLOAT, "NULLABLE"),
           bigquery.SchemaField("demo_pop", bigquery.enums.SqlTypeNames.INTEGER, "NULLABLE"),
           bigquery.SchemaField("avg_dist", bigquery.enums.SqlTypeNames.INTEGER, "NULLABLE"),
           bigquery.SchemaField("config_name", bigquery.enums.SqlTypeNames.STRING, "REQUIRED"),
           bigquery.SchemaField("config_set", bigquery.enums.SqlTypeNames.STRING, "REQUIRED"),
        ],
        clustering_fields = ['config_set', 'config_name']
    )
}
