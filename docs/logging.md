## Logging

### Working with code run from the command line interface

Currently the logging system in this project is a bit overly simplistic - they are print statements that are only run if the boolean variable "log" passed around is set to ```True```.  The logging used in the project is intended to work from the command line as well as from instances of Jupyter notebooks.  Processes may be run concurrently so simply writing to the screen or a single log file will not work since one process may print to the screen at the same time as another. As such, all screen prints are suppressed unless multiple concurrency is disabled AND verbose mode is specified (```-c0 -v``` on the command line).

When running from the command line, model_run.py will be called from model_run_cli.py.  model_run_cli.py will parse all the command line arguments and call the function ```run_on_config``` found in model_run.py using multiple concurrent processes as requested by the user based on the concurrency option ```-c```.  Each call concurrent to run_on_config will contain individual instances of ```PollingModelConfig``` from model_config.py which is a simple container class to pass all the configuration needed to run pyomo/SCIP.

When multiple concurrency is selected, as discussed further in the "To run" section of this document, logs will be written to the log directory specified by the user when run from the command line interface instead of the screen, typically the directory ```./logs``` instead of the screen.

PollingModelConfig will be setup with all the information needed to run a model, including where to write logs to in the variable ```log_file_path```, which is a string to the specific file that should be written (appended) to. The value of  ```log_file_path``` from PollingModelConfig is what is passed to pyomo so that it will write its log output to the correct location.   The individual log files will be named after the config file being run prefixed with a time stamp.  e.g. ```./logs/20231207151550_Gwinnett_config_original_2020.yaml.log```



### Using logs to debug

Until the logging system is updated to something more robust, any additional logging needed should be done with print statements that respect the ```logging``` boolean variable for use when concurrency is set to single threaded . Alternatively the file path ```log_file_path``` specified in the PollingModelConfig instance can be appended to.

If output from these log statements are needed then it is suggested that the command line be run in single concurrency mode with verbosity set to maximum e.g.:

```python
python ./model_run_cli.py -c1 -vv -l logs ./Gwinnett_GA_configs/Gwinnett_config_expanded_*.yaml
```

When running concurrently, logs can be followed from the log directory in realtime using something like the following in Linux/MacOS:

```bash
tail -f ./logs/20231207151550_Gwinnett_config_original_2020.yaml.log
```

