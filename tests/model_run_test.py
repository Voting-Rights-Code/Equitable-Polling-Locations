import os
import pandas as pd
from pathlib import Path
from model_config import PollingModelConfig
import model_data
import model_factory
import model_solver


TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TESTING_CONFIG_EXPANDED = os.path.join(TESTS_DIR, 'testing_config_expanded.yaml')

config = PollingModelConfig.load_config(TESTING_CONFIG_EXPANDED)
print(f'config -> {config}')
dist_df = model_data.clean_data(config, False)
alpha_df = model_data.clean_data(config, True)
alpha = model_data.alpha_min(alpha_df)

model = model_factory.polling_model_factory(dist_df, alpha, config)
model_solver.solve_model(model, config.time_limit)

def test_alpha_min():
    assert round(alpha, 11) ==  7.239801e-05 #value from R code

def test_kp_factor():
    dist_df['KP_factor'] = round(model_factory.compute_kp_factor(config, alpha, dist_df), 6)
    dist_df2 = dist_df[['id_orig', 'id_dest', 'KP_factor']]
    fixed_test_data = pd.read_csv('tests/test_kp_factor.csv') #data from R code
    fixed_test_data.kp_factor = round(fixed_test_data.kp_factor, 6)
    compare = dist_df2.merge(fixed_test_data, how = 'outer')
    assert compare.KP_factor.equals(compare.kp_factor)

def test_matching():
    matching_list= [(key[0], key[1]) for key in model.matching if model.matching[key].value ==1]
    assert matching_list == [(131350502312007, 'George Pierce Park Community Recreation Center'), (131350504421001, 'George Pierce Park Community Recreation Center'), (131350504273001, 'George Pierce Park Community Recreation Center'), (131350504522010, 'George Pierce Park Community Recreation Center'), (131350505221002, 'George Pierce Park Community Recreation Center'), (131350506174015, 'Bogan Park Community Recreation Center'), (131350503151002, 'George Pierce Park Community Recreation Center'), (131350505223003, 'George Pierce Park Community Recreation Center'), (131350505631006, 'George Pierce Park Community Recreation Center'), (131350501053055, 'Bogan Park Community Recreation Center')]

'''def tests_build_open_rule():
    # TODO change 5 to something appropriate
    open_rule = model_factory.precincts_open(5)

    model = create_test_model()
    # TODO change None
    assert open_rule(model) == 'Something' '''
