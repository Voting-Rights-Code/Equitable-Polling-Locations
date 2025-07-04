'''Note that this testing framework pulls a (fixed) sample dataset from an existing county, runs the model on it,
and checks that the resulta are consistent. As such, this is a point check only, and not a proof of correctness'''

# pylint: disable=redefined-outer-name

import math

import logging

import numpy as np
import pandas as pd
import pyomo.environ as pyo

from python.solver import model_factory, model_solver, model_run
from python.tests.constants import TEST_KP_FACTOR

pd.set_option('display.max_columns', None)

logger = logging.getLogger(__name__)


def load_kp_factor_data(path: str) -> pd.DataFrame:
    """Load the KP factor data from the test file."""
    dtype_spec = {
        'id_orig': 'string',
        'id_dest': 'string',
        'kp_factor': np.float64,
    }
    return pd.read_csv(path, dtype=dtype_spec)


def test_alpha_min(alpha_min):
    print(f'alpha -> {alpha_min}')
    print(f'alpha_min -> {alpha_min}')

    assert round(alpha_min, 11) ==  7.992335e-05 #value from R code

def test_kp_factor(alpha_min, distances_df, polling_locations_config):
    distances_kp = distances_df.copy()
    distances_kp['KP_factor'] = round(
        model_factory.compute_kp_factor(
            polling_locations_config,
            alpha_min,
            distances_df
        ),
        6,
    )

    distances_df2 = distances_kp[['id_orig', 'id_dest', 'KP_factor']]
    distances_df2['KP_factor'] = round(
        model_factory.compute_kp_factor(
            polling_locations_config,
            alpha_min,
            distances_df
        ),
        6,
    )

    distances_df2 = distances_df2.sort_values(by=['id_orig', 'id_dest'])

    fixed_test_data = load_kp_factor_data(TEST_KP_FACTOR) #data from R code
    fixed_test_data.kp_factor = round(fixed_test_data.kp_factor, 6)
    fixed_test_data = fixed_test_data.sort_values(by=['id_orig', 'id_dest'])

    compare = distances_df2.merge(fixed_test_data, how = 'outer', on=['id_orig', 'id_dest'])
    compare = compare.sort_values(by=['id_orig', 'id_dest'])

    assert compare.KP_factor.equals(compare.kp_factor)


# #test model constraints
def test_open_constraint(open_precincts, polling_locations_config):
    #number of open precincts as described in config
    assert len(open_precincts) == polling_locations_config.precincts_open


def test_max_new_constraint(potential_precincts, open_precincts, polling_locations_config):
    #number of new precincts less than maxpctnew of number open
    new_precincts = potential_precincts.intersection(open_precincts)
    print('new_precincts:', new_precincts)
    assert len(new_precincts) < polling_locations_config.maxpctnew * polling_locations_config.precincts_open


def test_min_old_constraint(distances_df, open_precincts, potential_precincts, polling_locations_config):
    #number of old precincts more than minpctold of old polls
    old_polls = len(distances_df[distances_df.location_type == 'polling'])
    old_precincts = open_precincts.difference(potential_precincts)
    assert len(old_precincts) >= polling_locations_config.minpctold*old_polls


def test_res_assigned(polling_model, distances_df):
    #each residence assigned to exactly one precinct
    #Note: ignoring the radius calculation here
    matched_residences = {key[0] for key in polling_model.matching if polling_model.matching[key].value ==1}

    all_residences = set(distances_df.id_orig.unique())

    assert matched_residences == all_residences


def test_precinct_open(polling_model, open_precincts):
    #residences matched to open precincts (and all open precincts matched)
    matched_precincts = {key[1] for key in polling_model.matching if polling_model.matching[key].value ==1}

    assert matched_precincts == open_precincts


def test_capacity(polling_model, distances_df, total_population, polling_locations_config):
    #each open precinct doesn't serve more that capacity * total pop / number open
    matching_list= [
        (key[0], key[1], polling_model.matching[key].value)
        for key in polling_model.matching
        if polling_model.matching[key].value ==1
    ]
    matching_df = pd.DataFrame(matching_list, columns = ['id_orig', 'id_dest', 'matching'])

    #merge with distances_df
    result_df = pd.merge(distances_df, matching_df, on = ['id_orig', 'id_dest'])
    dest_pop_df = result_df[['id_dest', 'population']].groupby('id_dest').agg('sum')
    # pylint: disable-next=line-too-long
    assert all(dest_pop_df.population <=(polling_locations_config.capacity*total_population/polling_locations_config.precincts_open))


# # Test the intermediate dataframe with driving distances
# # The test driving distances are exactly twice the haversine test distances
# def test_driving_distances(distances_df):
#     driving_config = PollingModelConfig.load_config(DRIVING_TESTING_CONFIG)
#     driving_polling_locations = model_data.get_polling_locations(
#         location_source=driving_config.location_source,
#         census_year=driving_config.census_year,
#         location=driving_config.location,
#         log_distance=driving_config.log_distance,
#             driving=driving_config.driving,
#     )
#     driving_polling_locations_df = driving_polling_locations.polling_locations
#     driving_dist_df = model_data.clean_data(driving_config, driving_polling_locations_df, False, False)

#     assert driving_dist_df['distance_m'].sum() == 2*distances_df['distance_m'].sum()


# Test for penalty functionality
def test_exclude_penalized(expanded_polling_model, polling_locations_penalty_config):
    ex_open_precincts = {key for key in expanded_polling_model.open if expanded_polling_model.open[key].value ==1}
    assert len(ex_open_precincts - set(polling_locations_penalty_config.penalized_sites))==3


def test_penalized_model(
    expanded_polling_model,
    polling_model,
    polling_locations_config,
    alpha_min,
    polling_locations_penalty_config,
    open_precincts,
    distances_df,
):
    ex_obj = pyo.value(expanded_polling_model.obj)
    print('polling_locations_config:', polling_locations_config.beta)
    ex_kp = -1/(polling_locations_config.beta*alpha_min)*math.log(ex_obj) # same beta and alpha for both configs

    obj = pyo.value(polling_model.obj)

    kp = -1/(polling_locations_config.beta*alpha_min)*math.log(obj)
    penalty = (ex_kp - kp) / len(open_precincts)
    pen_model = model_factory.polling_model_factory(distances_df, alpha_min, polling_locations_penalty_config,
                                                    exclude_penalized_sites=False,
                                                    site_penalty=penalty,
                                                    kp_penalty_parameter=kp)
    model_solver.solve_model(pen_model, polling_locations_penalty_config.time_limit)

    # PEN_OPEN_PRECINCTS = {key for key in pen_model.open if pen_model.open[key].value ==1}
    pen_obj = pyo.value(pen_model.obj)
    pen_kp = -1/(polling_locations_config.beta * alpha_min)*math.log(pen_obj) - penalty
    # print('pen_kp:', {pen_kp}, 'pen_obj:', {pen_obj})
    assert pen_kp > kp


def test_run_on_config(driving_testing_config):
    model_run.run_on_config(driving_testing_config, False, model_run.OUT_TYPE_CSV)
