from google.cloud import bigquery

project = "equitable-polling-locations"
dataset = "polling"
tables = ["result", "edes", "precinct_distances", "residence_distances"]

client = bigquery.Client()

for table in tables:

	view_id = project + "." + dataset + "." + table + "_extra"
	source_id = project + "." + dataset + "." + table 
	view = bigquery.Table(view_id)

	# The source table in this example is created from a CSV file in Google
	# Cloud Storage located at
	# `gs://cloud-samples-data/bigquery/us-states/us-states.csv`. It contains
	# 50 US states, while the view returns only those states with names
	# starting with the letter 'W'.
	view.view_query = f'''
	SELECT 
	  t.*,
	  c.location,
	  c.year,
	  c.precincts_open
	FROM polling.{table} t LEFT JOIN polling.configs c
	  ON t.config_name = c.config_name AND t.config_set = c.config_set
	'''

	# Make an API request to create the view.
	view = client.create_table(view)
	print(f"Created {view.table_type}: {str(view.reference)}")