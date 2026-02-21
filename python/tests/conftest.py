''' Pytest fixtures '''

# pylint: disable=redefined-outer-name,line-too-long

import os

import pandas as pd
import pytest

from python.solver import model_data, model_factory, model_run, model_solver, model_results, model_penalties
from python.solver.model_config import PollingModelConfig

from .constants import TESTING_CONFIG_BASE, TESTING_CONFIG_KEEP, TESTING_CONFIG_EXCLUDE, TESTING_CONFIG_PENALTY, TESTING_CONFIG_PENALTY_UNUSED, DRIVING_TESTING_CONFIG, TESTING_LOCATIONS_ONLY_PATH, TEST_LOCATION, MAP_SOURCE_DATE, POLLING_DIR

def generate_penalties_df(config: PollingModelConfig) -> pd.DataFrame:
    run_setup = model_run.prepare_run(config, False)

    model_solver.solve_model(run_setup.ea_model, config.time_limit, log=False, log_file_path=config.log_file_path)

    incorporate_result_df = model_results.incorporate_result(run_setup.dist_df, run_setup.ea_model, config.log_distance)

    penalize_model = model_penalties.PenalizeModel(run_setup=run_setup, result_df=incorporate_result_df)
    result = penalize_model.run()

    return result

@pytest.fixture(scope='session')
def driving_testing_config():
    return PollingModelConfig.load_config(DRIVING_TESTING_CONFIG)

@pytest.fixture(scope='session')
def testing_config_exclude():
    return PollingModelConfig.load_config(TESTING_CONFIG_EXCLUDE)

@pytest.fixture(scope='session')
def testing_config_penalty():
    return PollingModelConfig.load_config(TESTING_CONFIG_PENALTY)

@pytest.fixture(scope='session')
def testing_config_penalty_unused():
    return PollingModelConfig.load_config(TESTING_CONFIG_PENALTY_UNUSED)

@pytest.fixture(scope='session')
def testing_config_keep():
    return PollingModelConfig.load_config(TESTING_CONFIG_KEEP)

@pytest.fixture(scope='session')
def result_exclude_df(testing_config_exclude):
    return generate_penalties_df(testing_config_exclude)

@pytest.fixture(scope='session')
def result_penalized_df(testing_config_penalty):
    return generate_penalties_df(testing_config_penalty)

@pytest.fixture(scope='session')
def result_keep_df(testing_config_keep):
    return generate_penalties_df(testing_config_keep)

@pytest.fixture(scope='session')
def driving_locations_results_df(#tmp_path_factory, 
                                    driving_testing_config):
    ''' Fixture to load the locations results DataFrame from the testing locations CSV. '''

    #commenting out because I can't find tmp_path_factory
    #tmp_path = tmp_path_factory.mktemp('driving_locations_results_test_data')
    build_source_ouput_tmp_path = os.path.join(POLLING_DIR, driving_testing_config.location, 'testing_driving_distances_tmp.csv')

    model_data.build_source(
        'csv',
        census_year=driving_testing_config.census_year,
        location=driving_testing_config.location, # TEST_LOCATION,
        driving=driving_testing_config.driving,
        log_distance=driving_testing_config.log_distance,
        map_source_date=MAP_SOURCE_DATE,
        locations_only_path_override=TESTING_LOCATIONS_ONLY_PATH,
        output_path_override=build_source_ouput_tmp_path,
    )
    
    locations_results_df = model_data.load_locations_csv(build_source_ouput_tmp_path)
    
    return locations_results_df

@pytest.fixture(scope='session')
def polling_locations_config():
    yield PollingModelConfig.load_config(TESTING_CONFIG_BASE)

@pytest.fixture(scope='session')
def polling_locations_penalty_config():
    yield PollingModelConfig.load_config(TESTING_CONFIG_PENALTY)

@pytest.fixture(scope='module')
def polling_locations_df(polling_locations_config):
    polling_locations = model_data.get_polling_locations(
        location_source='csv',
        census_year=polling_locations_config.census_year,
        location=polling_locations_config.location,
        log_distance=polling_locations_config.log_distance,
        driving=polling_locations_config.driving,
    )
    yield polling_locations.polling_locations

@pytest.fixture(scope='module')
def distances_df(polling_locations_config, polling_locations_df):
    yield model_data.clean_data(polling_locations_config, polling_locations_df, False, False)

@pytest.fixture(scope='module')
def alpha_min(polling_locations_config, polling_locations_df):
    alpha_df = model_data.clean_data(polling_locations_config, polling_locations_df, True, False)
    yield model_data.alpha_min(alpha_df)

@pytest.fixture(scope='module')
def polling_model(distances_df, alpha_min, polling_locations_config):
    model = model_factory.polling_model_factory(distances_df, alpha_min, polling_locations_config)
    model_solver.solve_model(model, polling_locations_config.time_limit)

    yield model

#TODO: Should this be called the penaized polling model? where is this used?
@pytest.fixture(scope='module')
def expanded_polling_model(distances_df, alpha_min, polling_locations_penalty_config):
    model = model_factory.polling_model_factory(
        distances_df,
        alpha_min,
        polling_locations_penalty_config,
        exclude_penalized_sites=True
    )
    model_solver.solve_model(model, polling_locations_penalty_config.time_limit)

    yield model


@pytest.fixture(scope='module')
def open_precincts(polling_model):
    yield {key for key in polling_model.open if polling_model.open[key].value ==1}

@pytest.fixture(scope='module')
def total_population(distances_df):
    yield distances_df.groupby('id_orig')['population'].agg('unique').str[0].sum()

@pytest.fixture(scope='module')
def potential_precincts(distances_df):
    yield set(distances_df[distances_df.dest_type == 'potential'].id_dest)
