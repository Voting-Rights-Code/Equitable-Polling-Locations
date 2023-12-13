import os
import pandas as pd
from pathlib import Path
from model_config import PollingModelConfig
import model_data
import model_factory


TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TESTING_CONFIG_EXPANDED = os.path.join(TESTS_DIR, 'testing_config_expanded.yaml')


# TODO fill this out
def create_test_model():
    return 'Something'

def test_compute_kp_factor():
    config = PollingModelConfig.load_config(TESTING_CONFIG_EXPANDED)
    print(f'config -> {config}')
    dist_df = model_data.clean_data(config, False)
    alpha_df = model_data.clean_data(config, True)
    alpha = model_data.alpha_min(alpha_df)
    dist_df['KP_factor'] = round(model_factory.compute_kp_factor(config, alpha, dist_df), 6)
    dist_df2 = dist_df[['id_orig', 'id_dest', 'KP_factor']]
    fixed_test_data = pd.read_csv('tests/test_kp_factor.csv')
    fixed_test_data.kp_factor = round(fixed_test_data.kp_factor, 6)
    compare = dist_df2.merge(fixed_test_data, how = 'outer')

    assert compare.KP_factor.equals(compare.kp_factor)


'''def tests_build_open_rule():
    # TODO change 5 to something appropriate
    open_rule = model_factory.precincts_open(5)

    model = create_test_model()
    # TODO change None
    assert open_rule(model) == 'Something' '''
