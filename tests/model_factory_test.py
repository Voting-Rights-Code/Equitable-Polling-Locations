import os
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
    dist_df = model_data.clean_data(config)
    alpha  = model_data.alpha_min(dist_df)

    model_factory.compute_kp_factor(config, alpha, dist_df)

    # TODO correct assert
    assert alpha == 0.0005102569757533746


def tests_build_open_rule():
    # TODO change 5 to something appropriate
    open_rule = model_factory.precincts_open(5)

    model = create_test_model()
    # TODO change None
    assert open_rule(model) == 'Something'
