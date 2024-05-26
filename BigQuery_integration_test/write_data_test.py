from google.cloud import bigquery

# Construct a BigQuery client object.
client = bigquery.Client()

# TODO(developer): Set table_id to the ID of the table to create.
table_id = "voting-rights-storage-test.polling.edes"
file_path = "Berkeley_SC_Results_appended/Berkeley_SC_original_configs.Berkeley_config_original_2014_edes.csv"


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


job.result()  # Waits for the job to complete.

table = client.get_table(table_id)  # Make an API request.
print(
    "Loaded {} rows and {} columns to {}".format(
        table.num_rows, len(table.schema), table_id
    )
)