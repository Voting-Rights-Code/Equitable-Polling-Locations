''' Pytest fixtures '''

# pylint: disable=redefined-outer-name,line-too-long

import os

import pandas as pd
import pytest

from python.solver import model_data, model_factory, model_solver
from python.solver.model_run import ModelRun
from python.solver.model_config import PollingModelConfig

from .constants import (
  TESTING_CONFIG_BASE, TESTING_CONFIG_KEEP, TESTING_CONFIG_EXCLUDE, TESTING_CONFIG_PENALTY,
  TESTING_CONFIG_PENALTY_UNUSED, TESTING_CONFIG_DRIVING, TESTING_LOCATIONS_ONLY_PATH, MAP_SOURCE_DATE,
  POLLING_DIR,
)

def generate_penalties_df(config: PollingModelConfig) -> pd.DataFrame:
    model_run = ModelRun(config)
    # run_setup = model_run.prepare_run(config, False)

    # model_solver.solve_model(run_setup.ea_model, config.time_limit, log=False, log_file_path=config.log_file_path)

    # incorporate_result_df = model_results.incorporate_result(run_setup.dist_df, run_setup.ea_model)

    # penalize_model = model_penalties.PenalizeModel(run_setup=run_setup, result_df=incorporate_result_df)
    # result = penalize_model.run()

    return model_run.result_df

@pytest.fixture(scope='session')
def testing_config_driving():
    return PollingModelConfig.load_config(TESTING_CONFIG_DRIVING)

@pytest.fixture(scope='session')
def testling_config_base():
    yield PollingModelConfig.load_config(TESTING_CONFIG_BASE)


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
def location_df_with_driving(#tmp_path_factory,
                                    testing_config_driving):
    ''' Fixture to load the locations results DataFrame from the testing locations CSV. '''

    #commenting out because I can't find tmp_path_factory
    #tmp_path = tmp_path_factory.mktemp('driving_locations_results_test_data')
    build_source_ouput_tmp_path = os.path.join(POLLING_DIR, testing_config_driving.location, 'testing_driving_distances_tmp.csv')

    model_data.build_source(
        'csv',
        census_year=testing_config_driving.census_year,
        location=testing_config_driving.location, # TEST_LOCATION,
        driving=testing_config_driving.driving,
        log_distance=testing_config_driving.log_distance,
        map_source_date=MAP_SOURCE_DATE,
        locations_only_path_override=TESTING_LOCATIONS_ONLY_PATH,
        output_path_override=build_source_ouput_tmp_path,
    )

    location_df_driving = model_data.load_locations_csv(build_source_ouput_tmp_path)

    return location_df_driving


@pytest.fixture(scope='module')
def polling_locations_df(testling_config_base):
    polling_locations = model_data.get_polling_locations(
        location_source='csv',
        census_year=testling_config_base.census_year,
        location=testling_config_base.location,
        log_distance=testling_config_base.log_distance,
        driving=testling_config_base.driving,
    )
    yield polling_locations.polling_locations

@pytest.fixture(scope='module')
def distances_df(testling_config_base, polling_locations_df):
    yield model_data.clean_data(testling_config_base, polling_locations_df, False, False)

@pytest.fixture(scope='module')
def alpha_min(testling_config_base, polling_locations_df):
    alpha_df = model_data.clean_data(testling_config_base, polling_locations_df, True, False)
    yield model_data.alpha_min(alpha_df)

@pytest.fixture(scope='module')
def polling_model(distances_df, alpha_min, testling_config_base):
    model = model_factory.polling_model_factory(distances_df, alpha_min, testling_config_base)
    model_solver.solve_model(model, testling_config_base.time_limit)

    yield model

#TODO: Should this be called the penaized polling model? where is this used?
@pytest.fixture(scope='module')
def expanded_polling_model(distances_df, alpha_min, testing_config_penalty):
    model = model_factory.polling_model_factory(
        distances_df,
        alpha_min,
        testing_config_penalty,
        exclude_penalized_sites=True
    )
    model_solver.solve_model(model, testing_config_penalty.time_limit)

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
