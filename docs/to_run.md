## Execution

From command line:

First activate the environment if not done so already:
```bash
    conda activate equitable-polls
```

Then create the requisite input files discussed in the [previous section](input_files.md).

Next run the model.
* There are two command line options, one to write data locally, and the other to write data to the database
    * Read/write locally: 
        * Specified file list `python -m python.scripts.model_run_cli -c NUM -l LOG_DIR datasets/config/<config_set>/<config_name1>.yaml datasets/config/<config_set2>/<config_name>.yaml`
        * All files in a config set `python -m python.scripts.model_run_cli -c NUM -l LOG_DIR datasets/config/<config_set>/*.yaml` Note the `.yaml`
    * Read/write from/to database if the appropriate [intermediate dataset](intermediate_datasets.md) has been created:
        * Specified file list `python -m python.scripts.model_run_db_cli -c NUM -l LOG_DIR <config_set>/<config_name1> <config_set2>/<config_name>`
        * All files in a config set `python -m python.scripts.model_run_db_cli -c NUM -l LOG_DIR <config_set>`
            * When prompted, enter `equitable-polling-locations` for the project (default) and `equitable_polling_locations_prod` (or appropriate scratch dataset name) for dataset.
            * If you do not want to write the outputs to the indicated datase, use the flag `-o csv` to write outputs locally.
    * Read/write from/to database if not all files are already stored in the cloud:
        * If the locations only file is not stored on the cloud:
            * Run `python -m python.scripts.db_import_locations_only_cli <list of locations for which polling location data will be uploaded>`
            * See [database](database.md) for more details.
        * If the driving distances file is needed but not stored on the cloud:
            * Run `python -m python.scripts.db_import_driving_distances_cli <census year> <list of locations for which driving distance data will be uploaded>`
            * See [database](database.md) for more details.
        * If the appropriate [intermediate dataset](intermediate_datasets.md) does not exist:
            * Run `python.scripts.db_import_locations_cli <census year> <list of locations for which  intermediate datasets should be created> -t <distance type> -d <map date for driving distances>`. 
            * See [intermediate datasets](intermediate_datasets.md) and [database](database.md) for more details.

The parameters for `model_run_db_cli` are as follows:
* LOG_DIR = Where to put log files. 
    * The directory must exist, or the program will not run
* NUM = number of cores to run the model on.
    * Default = 1. 
    * Cannot multi-thread the individual runs. 
    * Multi-thread does not work on window machines 
* path to config file accepts wild cards to set of sequential runs
    * config_set and config_name refer to the fields in the config data.
* To write files locally while using `model_run_db_cli`, use the flag `-o csv`
* For extra logging written to screen include the flag `-vv`. This only works for one core

### Examples

Default execution:\
```python -m python.scripts.model_run_db_cli -h```

To run all configs in the config_set `Gwinnett_County_GA_driving_no_bg_no_ed_configs`, from the database, parallel processing 4 at a time, and write log files out to the logs directory:\
```python -m python.scripts.model_run_db_cli -c4 -l logs Gwinnett_County_GA_driving_no_bg_no_ed_configs```

To run all configs in the config_set Gwinnett_County_GA_driving_no_bg_no_ed_configs locally, one at a time, with extra logging printed to the console, and write log files out to the logs directory:\
```python -m python.scripts.model_run_db_cli -vv -l logs datasets/configs/Gwinnett_County_GA_driving_no_bg_no_ed_configs/*.yaml```

To run only the config Gwinnett_County_GA_driving_no_bg_no_ed_14 from the database and write log files out to the logs directory:\
```python -m python.scripts.model_run_db_cli -l logs Gwinnett_County_GA_driving_no_bg_no_ed_configs/Gwinnett_County_GA_driving_no_bg_no_ed_14.yaml```


***NOTE: BEWARE OF CAPITALIZATION***  
Both Gwinnett_G**A**_configs/Gwinnett* and Gwinnett_G**a**_configs/Gwinnett* will run on Windows. However, due to string replacement work in other parts of the programs, the former is preferred.


<!--### From Google Colab:
Follow the the instructions in [this file](/Colab_runs/colab_Gwinnett_expanded_multi_11_12_13_14_15.ipynb)-->
