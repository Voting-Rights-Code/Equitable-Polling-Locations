'''Note that this testing framework pulls a (fixed) sample dataset from an existing county, runs the model on it,
and checks that the resulta are consistent. As such, this is a point check only, and not a proof of correctness'''

# pylint: disable=redefined-outer-name

import logging

import numpy as np
import pandas as pd

from python.solver import model_factory
from python.solver.model_run import ModelRun
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
    distances_kp['kp_factor'] = round(
        model_factory.compute_kp_factor(
            polling_locations_config,
            alpha_min,
            distances_df
        ),
        6,
    )

    distances_df2 = distances_kp[['id_orig', 'id_dest', 'kp_factor']]
    distances_df2['kp_factor'] = round(
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

    assert compare.kp_factor_x.equals(compare.kp_factor_y)


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


def test_run_on_config(driving_testing_config):
    # model_run.run_on_config(driving_testing_config, False, model_run.OUT_TYPE_CSV)
    model_run = ModelRun(config=driving_testing_config)
    model_run.write_results_csv()
