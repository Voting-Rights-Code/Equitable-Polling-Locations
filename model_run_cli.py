''' Command line util to run models '''

from multiprocessing import Pool
import os
import sys
import model_run
from polling_model_config import PollingModelConfig

# #get config folder from command line
CONFIG_FOLDER = sys.argv[1]

MULTI_PROCESS = True
MULTI_PROCESS_CONCURRENT = 2

# Get the list of config files from the folder specified on the command line
config_list = [ os.path.join(CONFIG_FOLDER, file) for file in os.listdir(CONFIG_FOLDER) ]

if MULTI_PROCESS:
    with Pool(MULTI_PROCESS_CONCURRENT) as pool:
        run_configs = [ PollingModelConfig.load_config(run_config) for run_config in config_list ]
        processed = pool.map(model_run.run_on_config, run_configs)
else:
    for config_file in config_list:
        run_config = PollingModelConfig.load_config(config_file)
        model_run.run_on_config(run_config)
