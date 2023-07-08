#Imports to get / print the new model
from test_config_refactor import * #For testing only. Remove later 
from build_model import build_model

SA_model = build_model()
with open('sa_model.txt', 'w') as output_file:
            SA_model.pprint(output_file)


import test_config_refactor as config
from model_factory import polling_model_factory

factory_model = polling_model_factory(config)
with open('factory_model.txt', 'w') as output_file:
            factory_model.pprint(output_file)