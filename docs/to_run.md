## Execution

From command line:

First activate the environment if not done so already:
```bash
    conda activate equitable-polls
```

* There are two command line options, one to write data locally, and the other to write data to the database
    * Read/write locally: `python3 run.py python.scripts.model_run_cli -c NUM -l ./path/to/config/file.yaml`
    * Read/write from/to database:
        * `python3 run.py python.scripts.model_run_db_cli -e ENV -c NUM -l config_set/config_name1 config_set2/config_name`
        * `python3 run.py python.scripts.model_run_db_cli -e ENV -c NUM -l config_set`
    * Parameters
        * ENV = The environment to use. For cli utilities that connect to the database, you need to select an environment.  Typically this will be "prod" but others can be defined in settings.yaml in the project root directory. If an environment is not defined then you will be prompted to pick one.
        * NUM = The number of configurations to run concurrently (default = 1).  If more than one is then multiple model runs can potentially be completed quicker depending on the resources available on your computer.
        * path to config file accepts wild cards to set of sequential runs
        * config_set and config_name refer to the fields in the config data.
            * To run all the config_names associated to a config_set, just enter the config_set
    * For extra logging include the flag -vv



### Examples

Default execution:\
```python3 run.py python.scripts.model_run_db_cli -h```

To run all expanded configs, parallel processing 4 at a time, and write log files out to the logs directory:\
```python3 run.py python.scripts.model_run_db_cli -c4 -l ./Gwinnett_GA_configs/Gwinnett_config_expanded_*.yaml```

To run all full configs run one at a time, extra logging printed to the console, and write log files out to the logs directory:\
```python3 run.py python.scripts.model_run_db_cli -vv -l ./Gwinnett_GA_configs/Gwinnett_config_full_*.yaml```

To run only the full_11 and write log files out to the logs directory:\
```python3 run.py python.scripts.model_run_db_cli -l ./Gwinnett_GA_configs/Gwinnett_config_full_11.yaml```


***NOTE: BEWARE OF CAPITALIZATION***  Both ./Gwinnett_G**A**_configs/Gwinnett* and ./Gwinnett_G**a**_configs/Gwinnett* will run on Windows. However, due to string replacement work in other parts of the programs, the former is preferred.


### From Google Colab:
Follow the the instructions in [this file](/Colab_runs/colab_Gwinnett_expanded_multi_11_12_13_14_15.ipynb)
