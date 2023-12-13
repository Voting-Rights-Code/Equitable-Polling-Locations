import os
from pathlib import Path
from model_config import PollingModelConfig
import model_data


TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TESTING_CONFIG_EXPANDED = os.path.join(TESTS_DIR, 'testing_config_expanded.yaml')

def test_alpha_min():
    config = PollingModelConfig.load_config(TESTING_CONFIG_EXPANDED)
    print(f'config -> {config}')
    alpha_df = model_data.clean_data(config)
    alpha  = model_data.alpha_min(alpha_df)

    assert alpha == 0.0005102569757533746

# TODO: Work in progress, Susama please finish
def test_alpha_new():
    config = PollingModelConfig.load_config(TESTING_CONFIG_EXPANDED)
    print(f'config -> {config}')
    alpha_df = model_data.clean_data(config)
    alpha  = model_data.alpha_min(alpha_df)

    ea_model = model_data.polling_model_factory(dist_df, alpha, config)

    model_data.solve_model(ea_model, config.time_limit, log=log, log_file_path=config.log_file_path)
    result_df = model_data.incorporate_result(dist_df, ea_model)

    assert alpha == 0.0005102569757533746
