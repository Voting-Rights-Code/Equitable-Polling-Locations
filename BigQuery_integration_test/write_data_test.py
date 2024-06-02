from google.cloud import bigquery

# Construct a BigQuery client object.
client = bigquery.Client()

# TODO(developer): Set table_id to the ID of the table to create.
table_names = [
    "edes",
    "result",
    "precinct_distances",
    "residence_distances"
]
project_dataset = "voting-rights-storage-test.polling"
csv_stem = "Berkeley_SC_Results_appended/Berkeley_SC_original_configs.Berkeley_config_original_2014"

# TODO: Check whether a given run name already exists

for table_name in table_names:
    table_id = project_dataset + "." + table_name
    file_path = csv_stem + "_" + table_name + ".csv"

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