''' Command line util to run models '''

from multiprocessing import Pool
import os
import sys
import model_run

# #get config folder from command line
CONFIG_FOLDER = sys.argv[1]

MULTI_PROCESS = True
MULTI_PROCESS_CONCURRENT = 2

#get list of config files from the folder specified on the command line
config_list = [ os.path.join(CONFIG_FOLDER, file) for file in os.listdir(CONFIG_FOLDER) ]

if MULTI_PROCESS:
    with Pool(MULTI_PROCESS_CONCURRENT) as pool:
        processed = pool.map(model_run.run_on_config, config_list)
else:
    for config_file in config_list:
        # config = importlib.import_module(config_file)
        run_config = model_run.load_config(config_file)
        model_run.run_on_config(run_config)
