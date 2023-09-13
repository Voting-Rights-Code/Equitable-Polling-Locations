#Imports to get / print the new model
#from test_config_refactor import * #For testing only. Remove later 
#from build_model import build_model

'''SA_model = build_model()
with open('sa_model.txt', 'w') as output_file:
            SA_model.pprint(output_file)


import test_config_refactor as config
from model_factory import polling_model_factory

factory_model = polling_model_factory(config)
with open('factory_model.txt', 'w') as output_file:
            factory_model.pprint(output_file)'''

import equal_access_model as ea
from test_config import *
import importlib

importlib.reload(ea)

'''CITY = 'Test'
YEAR = '2016'
LEVEL = 'full'
#BETA = -2
TIME_LIMIT = 120 #2 minutes
MAXPCTNEW = .5'''

print(f'time limit set as {TIME_LIMIT} in config file')
for BETA in BETA_LIST:
    ea.optimize(CITY, YEAR, LEVEL, BETA, maxpctnew=MAXPCTNEW, time_limit=TIME_LIMIT)