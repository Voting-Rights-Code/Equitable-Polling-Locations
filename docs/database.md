# Database

The default Google Cloud project used by the Voting Rights Code Group is ```equitable-polling-locations```.  To see the existing data in the Google Cloud Console, [click here](https://console.cloud.google.com/bigquery?ws=!1m4!1m3!3m2!1sequitable-polling-locations!2sequitable_polling_locations_prod). Access may be requested by reaching out to Voting Rights Code team members.

The output from the optimization model runs can be found in the BigQuery dataset equitable_polling_locations_prod.

## Schema and Tables Relationships

 All data written to the equitable_polling_locations_prod is intended to be immutable and, as such, there are no overwrites or deletions from subsequent runs against the same dataset.  Instead any time new optimization model data output is written, first an entry in the ```model_runs``` table is created and that will link the config used to all output tables.



| Name                       | Type  | Purpose                                                                            |
|----------------------------|-------|------------------------------------------------------------------------------------|
| model_configs              | Table | The config settings used to generate the optimization model output                 |
| model_runs                 | Table | Any time a model run is executed from a config, a new entry in model_runs is created.|
| model_config_runs          | View  | A view that inner joins model_configs and model_runs while only including the most recent and successful model_runs, avoiding any outdated data or incomplete output.
| edes                       | Table | The ede results from the optimization model run |
| edes_extras                | View  | A view that inner joins model_config_runs and edes                                 |
| precinct_distances         | Table | The precinct distances from the optimization model run |
| precinct_distances_extras  | View  | A view that inner joins model_config_runs and precinct_distances                   |
| residence_distances        | Table | The residence distances from from the optimization model run |
| residence_distances_extras | View  | A view that inner joins model_config_runs and residence_distances_extras           |
| results                    | Table | The general results from the from the optimization model run |
| results_extras             | View  | A view that inner joins model_config_runs and residence_distances_extras           |
| polling_locations_only     | Table | The polling location only data source |
| polling_locations_only_sets | Table | The metadata for polling location only data source |
| driving_distances          | Table | The driving distances for polling locations data source|
| driving_distance_sets      | Table | The metadata for driving distances for polling locations data source |
| polling_locations          | Table | The polling locations data source used by the optimizer |
| polling_locations_sets     | Table | The metadata for polling locations data |




### model_configs and model_runs
* One-to-Many Relationship:
  * A single model_configs record can have many associated model_runs records.
  * Each model_runs record belongs to exactly one model_configs record.

### model_runs and Related Tables
* One-to-Many Relationships:
  *  A single model_runs record can have many associated records in the following tables:
    *  results
    *  edes
    *  precinct_distances
    *  residence_distances

### Example Queries

Find all configs for for the config_set `Chatham_County_GA_no_bg_school_configs`:
```sql
SELECT *
  FROM `equitable-polling-locations.equitable_polling_locations_prod.model_config_runs`
 WHERE config_set = 'Chatham_County_GA_no_bg_school_configs';
```

Find all ede values for the config_set `Chatham_County_GA_no_bg_school_configs`, and config_name `Chatham_config_no_school_20`:
```sql
SELECT *
  FROM `equitable-polling-locations.equitable_polling_locations_prod.edes_extras`
 WHERE config_set = 'Chatham_County_GA_no_bg_school_configs'
   AND config_name = 'Chatham_config_no_school_20';
```


## BigQuery Table Management

Tables for the Equitable-Polling-Locations project are managed using Python's [SQLAlchemy](https://www.sqlalchemy.org/) and the [Alemebic](https://alembic.sqlalchemy.org/en/latest/) migration tool. See the folder `.../models` and `.../alembic` in this repository.  For example, the definition of the model_configs and model_runs tables can be found in `.../models/model_config.py`.

### Setup a new database or upgrading an existing one with the latest schema

Setting up a new database to work against is useful for development and testing.

To setup a new database:
1. Create a new dataset using the the [Google BigQuery Cloud Console](https://console.cloud.google.com/bigquery).
2. Activate conda `$ conda activate equitable-polls` (see earlier instructions)
3. Use the alembic upgrade command `$ alembic upgrade head`
4. (When prompted enter the project and dataset that was created if DB_PROJECT and/or DB_dataset were not set in the environment.)


### Adding a columns to an existing table

Alembic will manage the changes needed for database updates.

**NOTE:** Development and code changes involving updates to the database should be tested in scratch datasets, and only applied to the `equitable_polling_locations_prod` dataset after a code review and merge has been accepted.

1. Open the desired SQLALchemy model in the `.../models` directory.
2. Add a new column(s) as appropriate
3. Activate conda `$ conda activate equitable-polls` (see earlier instructions)
4. When complete, run the following alembic command to create a new migration.  `$ alembic revision --autogenerate -m "A SMALL DESCRIPTION OF YOUR CHANGES HERE"`.  This will create a new migration file in `.../alembic/versions` named after your description.
5. Alembic will create lines in your new migration file that looks similar to `op.create_foreign_key(None, 'model_runs', 'model_configs', ['model_config_id'], ['id'])` and `op.drop_constraint(None, 'model_runs', type_='foreignkey')`, these will need to be removed to work with BigQuery.
6. Upgrade your scratch database `$ alembic upgrade head`
7. Commit your changes in `.../models` and the added files in `.../alembic/versions` to git as appropriate

[See alembic documentation](https://alembic.sqlalchemy.org/en/latest/tutorial.html) for more information on migration management and command line options, including how to downgrade the database.

### Adding a new tables

Alembic will manage the changes needed for adding new database tables.

**NOTE:** Development and code changes involving updates to the database should be tested in scratch datasets, and only applied to the `equitable_polling_locations_prod` dataset after a code review and merge has been accepted.

1. Open the desired SQLALchemy model in the `.../models` directory.
2. Create a new model file(s) as appropriate
3. Update `.../models/__init__.py` to include your new model file(s)
4. Activate conda `$ conda activate equitable-polls` (see earlier instructions)
5. When complete, run the following alembic command to create a new migration.  `$ alembic revision --autogenerate -m "A SMALL DESCRIPTION OF YOUR CHANGES HERE"`.  This will create a new migration file in `.../alembic/versions` named after your description.
6. Upgrade your scratch database `$ alembic upgrade head`
7. Commit your changes in `.../models` and the added files in `.../alembic/versions` to git as appropriate

[See alembic documentation](https://alembic.sqlalchemy.org/en/latest/tutorial.html) for more information on migration management and command line options, including how to downgrade the database.

## Database Access

You must have a google account with access to a Google cloud project.

### Granting Read Only Access for Analysis

Someone with owner access to the ```equitable-polling-locations``` project can grant read only access to the datasets by:
* Going to the equitable_polling_locations_prod [dataset from the console](https://console.cloud.google.com/bigquery?ws=!1m4!1m3!3m2!1sequitable-polling-locations!2sequitable_polling_locations_prod).
* Under the explorer menu, and click: the vertical elipses -> Share -> Manage Permissions -> ADD PRINCIPAL.
* From the Add Principal menu, invite the person to be added and include the roles "Big Query Data Viewer"

With read only access, the user can

**NOTE:** the principal will need their own or an existing Google Project they have access to in order for BigQuery to bill that project (as opposed to billing the equitable-polling-locations for queries), so a google email account is recommended.  For more details on permissions [watch this video](https://www.youtube.com/watch?v=YfXm3_VsFXY&list=PLFHcsNl_5q_8FGF2nsU6YCXAaCMeQjmsG&index=2).


## Selecting which database to write to

When using the model_run_cli.py scripts as well as Alembic for database migrations, the The Google Project
and BigQuery dataset can be selected by setting the environemntal variables DB_PROJECT and DB_dataset.
If these variables are not set then you will be prompted to chooose which project and which dataset to use.

Setting Project and dataset for Linux/MacOS
```bash
export DB_PROJECT=equitable-polling-locations
export DB_DATASET=equitable_polling_locations_prod
```

Setting Project and dataset for Windows
```bash
set DB_PROJECT=equitable-polling-locations
set DB_DATASET=equitable_polling_locations_prod
```

## Writting model run output to the database

To write ouput from the

python.scripts.model_run_db_cli will write to output the to Google's BigQuery by default unless -o csv is selected.

Example:

```
python -m python.scripts.model_run_db_cli -vv Contained_in_Madison_City_of_WI_potential_configs_driving/Contained_in_Madison_City_of_WI_config_driving_change_1
```

# Database Imports

## Dataset Import Tools

In order to run python.scripts.model_run_db_cli, the required datasources for the giving location must be imported into the database.  These imports should occur in the following order:
1. Polling Locations Only File Imports
1. Driving Distance Imports (only if driving distances will be required)
1. Build and Import Locations with Distances

The import tools may be run more than once any location.  Reruns will not overwrite historic imports, so they will be available for historic purposes.  However, anytime the import tools are used to reimport a datasets then the subsequent import tools must be also rerun.  For example, if "Driving Distance Imports" for a given location are rerun then "Build and Import Locations with Distances" must also be rerun afterwards for the same location in order for that data to be made available to the model_run_db_cli script.

### Polling Locations Only File Imports

Polling locations only csv files, located in ```.../datasets/polling/[location]/```, represent a growing list of polling locations throught the years.  These locations do not include distances to each group. These locations only files must be imported into the database before any of the rest of the dataset database imports.

Example of importing the latest Contained_in_Madison_City_of_WI and Gwinnett_County_GA locations only:

```
python -m python.scripts.db_import_locations_only_cli Contained_in_Madison_City_of_WI Gwinnett_County_GA
```

Any errors importing will be written to the screen as well as the logs directory (by default) to the file `.../logs/locations_only_import_errors.csv`.

### Driving Distance Imports

Driving distance csv files, located in ```.../datasets/driving/[location]/```, are needed for running optimization models where driving is set to true in the model config.

Example of importing the latest Contained_in_Madison_City_of_WI and Gwinnett_County_GA driving for the 2020 census year:

```
python -m python.scripts.db_import_driving_distances_cli 2020 Contained_in_Madison_City_of_WI Gwinnett_County_GA
```

Any errors importing will be written to the screen as well as the logs directory (by default) to the file `.../logs/driving_distance_import_errors.csv`.


### Build and Import Locations with Distances

Locations which include distances are what the optimizer will run against using the model_run_db_cli script.  Locations with distances can be log or linear distance, and haversine or driving distance.

Example of building and importing the latest Contained_in_Madison_City_of_WI and Gwinnett_County_GA linear, haversine locations for 2020 census year:

```
python -m python.scripts.db_import_locations_cli -t linear 2020 Contained_in_Madison_City_of_WI Gwinnett_County_GA
```

Example of building and importing the latest Contained_in_Madison_City_of_WI and Gwinnett_County_GA log, haversine locations for 2020 census year:

```
python -m python.scripts.db_import_locations_cli -t log 2020 Contained_in_Madison_City_of_WI Gwinnett_County_GA
```

Example of building and importing the latest Contained_in_Madison_City_of_WI and Gwinnett_County_GA linear, driving locations for 2020 census year:

```
python -m python.scripts.db_import_locations_cli -d -t linear 2020 Contained_in_Madison_City_of_WI Gwinnett_County_GA
```

Example of building and importing the latest Contained_in_Madison_City_of_WI and Gwinnett_County_GA log, driving locations for 2020 census year:

```
python -m python.scripts.db_import_locations_cli -d -t log 2020 Contained_in_Madison_City_of_WI Gwinnett_County_GA
```

Any errors importing will be written to the screen as well as the logs directory (by default) to the file `.../logs/locations_import_errors.csv`.



## Import existing model run csv result files into the BigQuery database

To import existing csv files into the BigQuery database, use the db_import_cli.py script.

Here is an example of importing all results from Berkeley_County_SC_original_configs:

```
python -m python.scripts.db_import_cli ./Berkeley_County_SC_original_configs/*.yaml
```

Any errors importing will be written to the screen as well as the logs directory (by default) to the file `.../logs/import_errors.csv`.
