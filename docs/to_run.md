## Execution

From command line:

First activate the environment if not done so already:
```bash
    conda activate equitable-polls
```

* There are two command line options, one to write data locally, and the other to write data to the database
    * Read/write locally: 
        * Specified file list `python -m python.scripts.model_run_cli -c NUM -l LOG_DIR datasets/config/<config_set>/<config_name1>.yaml datasets/config/<config_set2>/<config_name>.yaml`
        * All files in a config set `python -m python.scripts.model_run_cli -c NUM -l LOG_DIR datasets/config/<config_set>/*.yaml` Note the `.yaml`
    * Read/write from/to database:
        * Specified file list `python -m python.scripts.model_run_db_cli -c NUM -l LOG_DIR <config_set>/<config_name1> <config_set2>/<config_name>`
        * All files in a config set `python -m python.scripts.model_run_db_cli -c NUM -l LOG_DIR <config_set>`
        * It is possible that the requisite [intermediate datasets](intermediate_datasets.md) is not in the database. In this case, the above commands will give instruct the user to run `python.scripts.db_import_locations_cli`. See [intermediate datasets](intermediate_datasets.md) for more details.
    * Parameters
        * LOG_DIR = Where to put log files. 
            * The directory must exist, or the program will not run
        * NUM = number of cores to run the model on.
            * Default = 1. 
            * Cannot multi-thread the individual runs. 
            * Multi-thread does not work on window machines 
        * path to config file accepts wild cards to set of sequential runs
            * config_set and config_name refer to the fields in the config data.
    * For extra logging include the flag -vv.
        Only works for one core

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
