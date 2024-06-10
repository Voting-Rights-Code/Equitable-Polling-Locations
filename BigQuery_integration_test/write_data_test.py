from google.cloud import bigquery

# Construct a BigQuery client object.
client = bigquery.Client()

out_types= [
    "configs",
    "edes",
    "result",
    "precinct_distances"
    #"residence_distances", # residence distance table has bad NA values for now
]
config_set = "York_SC_original_configs"
in_dir = config_set + "_collated"


# Don't change this, it's the server-side name
project_dataset = "voting-rights-storage-test.polling"
# TODO: Check whether a given run name already exists

for out_type in out_types:
    table_id = project_dataset + "." + out_type
    file_path = in_dir + "/" + config_set + "_" + out_type + ".csv"

    job_config = bigquery.LoadJobConfig(
        source_format=bigquery.SourceFormat.CSV, 
        skip_leading_rows=1, 
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )

    with open(file_path, "rb") as source_file:
        job = client.load_table_from_file(
            source_file, 
            table_id, 
            job_config=job_config
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