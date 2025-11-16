'''Note that this testing framework pulls a (fixed) sample dataset from an existing county, runs the model on it,
and checks that the resulta are consistent. As such, this is a point check only, and not a proof of correctness'''

# pylint: disable=redefined-outer-name

import logging

import numpy as np
import pandas as pd
import os

from python.solver import model_factory
from python.solver.model_run import ModelRun
from python.tests.constants import TEST_KP_FACTOR, TESTING_RESULTS_DIR, TESTING_CONFIG_BASE

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
    
    assert round(alpha_min, 11) ==  7.992335e-05 #value from R code

def test_kp_factor(alpha_min, clean_distances_df, testing_config_base):
    distances_kp = clean_distances_df.copy()
    distances_kp['kp_factor'] = round(
        model_factory.compute_kp_factor(
            testing_config_base,
            alpha_min,
            clean_distances_df
        ),
        6,
    )

    distances_kp = distances_kp.sort_values(by=['id_orig', 'id_dest'])

    fixed_test_data = load_kp_factor_data(TEST_KP_FACTOR) #data from R code
    fixed_test_data.kp_factor = round(fixed_test_data.kp_factor, 6)
    fixed_test_data = fixed_test_data.sort_values(by=['id_orig', 'id_dest'])

    compare = distances_kp.merge(fixed_test_data, how = 'outer', on=['id_orig', 'id_dest'])
    compare = compare.sort_values(by=['id_orig', 'id_dest'])

    assert compare.kp_factor_x.equals(compare.kp_factor_y)


# #test model constraints
def test_open_constraint(open_precincts, testing_config_base):
    #number of open precincts as described in config
    assert len(open_precincts) == testing_config_base.precincts_open


def test_max_new_constraint(potential_precincts, open_precincts, testing_config_base):
    #number of new precincts less than maxpctnew of number open
    new_precincts = potential_precincts.intersection(open_precincts)
    print('new_precincts:', new_precincts)
    assert len(new_precincts) < testing_config_base.maxpctnew * testing_config_base.precincts_open


def test_min_old_constraint(clean_distances_df, open_precincts, potential_precincts, testing_config_base):
    #number of old precincts more than minpctold of old polls
    old_polls = len(clean_distances_df[clean_distances_df.location_type == 'polling'])
    old_precincts = open_precincts.difference(potential_precincts)
    assert len(old_precincts) >= testing_config_base.minpctold*old_polls


def test_res_assigned(polling_model, clean_distances_df):
    #each residence assigned to exactly one precinct
    #Note: ignoring the radius calculation here
    matched_residences = {key[0] for key in polling_model.matching if polling_model.matching[key].value ==1}

    all_residences = set(clean_distances_df.id_orig.unique())

    assert matched_residences == all_residences


def test_precinct_open(polling_model, open_precincts):
    #residences matched to open precincts (and all open precincts matched)
    matched_precincts = {key[1] for key in polling_model.matching if polling_model.matching[key].value ==1}

    assert matched_precincts == open_precincts


def test_capacity(polling_model, clean_distances_df, total_population, testing_config_base):
    #each open precinct doesn't serve more that capacity * total pop / number open
    matching_list= [
        (key[0], key[1], polling_model.matching[key].value)
        for key in polling_model.matching
        if polling_model.matching[key].value ==1
    ]
    matching_df = pd.DataFrame(matching_list, columns = ['id_orig', 'id_dest', 'matching'])

    #merge with clean_distances_df
    result_df = pd.merge(clean_distances_df, matching_df, on = ['id_orig', 'id_dest'])
    dest_pop_df = result_df[['id_dest', 'population']].groupby('id_dest').agg('sum')
    # pylint: disable-next=line-too-long
    assert all(dest_pop_df.population <=(testing_config_base.capacity*total_population/testing_config_base.precincts_open))


def test_result_df(testing_config_base):
    # test that the result_df is correct
    model_run = ModelRun(testing_config_base)
    test_result_data = model_run.result_df
    
    file_name = testing_config_base.location + '.' + testing_config_base.config_name + '_results.csv'
    file_result_data = pd.read_csv(os.path.join(TESTING_RESULTS_DIR, file_name), index_col = 0)
    #convert ints to str for consistency
    file_result_data['id_orig'] = file_result_data['id_orig'].astype(str)
    #round to rid floating point errors
    test_result_data['weighted_dist'] = test_result_data['weighted_dist'].round(9)
    file_result_data['weighted_dist'] = file_result_data['weighted_dist'].round(9)

    pd.testing.assert_frame_equal(left=test_result_data, right=file_result_data, check_exact=True)
    


def test_precinct_dist_df(testing_config_base):
    #test that the precinct_distance_df is correct
    model_run = ModelRun(testing_config_base)
    test_precinct_dist_data = model_run.demographic_prec.reset_index()
    file_name = testing_config_base.location + '.' + testing_config_base.config_name + '_precinct_distances.csv'
    file_precinct_dist_data = pd.read_csv(os.path.join(TESTING_RESULTS_DIR, file_name), index_col= 0).reset_index()
    
    #round to rid floating point errors
    test_precinct_dist_data['weighted_dist'] = test_precinct_dist_data['weighted_dist'].round(9)
    test_precinct_dist_data['avg_dist'] = test_precinct_dist_data['avg_dist'].round(9)
    file_precinct_dist_data['weighted_dist'] = file_precinct_dist_data['weighted_dist'].round(9)
    file_precinct_dist_data['avg_dist'] = file_precinct_dist_data['avg_dist'].round(9)
    pd.testing.assert_frame_equal(left=test_precinct_dist_data, right=file_precinct_dist_data, check_exact=True)

def test_residence_dist_df(testing_config_base):
    #test that the residence_distance_df is correct
    
    model_run = ModelRun(testing_config_base)
    test_residence_dist_data = model_run.demographic_res.reset_index()
    file_name = testing_config_base.location + '.' + testing_config_base.config_name + '_residence_distances.csv'
    file_residence_dist_data = pd.read_csv(os.path.join(TESTING_RESULTS_DIR, file_name), index_col= 0).reset_index()

    #convert ints to str for consistency
    file_residence_dist_data['id_orig'] = file_residence_dist_data['id_orig'].astype(str)
    #round to rid floating point errors
    test_residence_dist_data['weighted_dist'] = test_residence_dist_data['weighted_dist'].round(9)
    test_residence_dist_data['avg_dist'] = test_residence_dist_data['avg_dist'].round(9)
    
    file_residence_dist_data['weighted_dist'] = file_residence_dist_data['weighted_dist'].round(9)
    file_residence_dist_data['avg_dist'] = file_residence_dist_data['avg_dist'].round(9)
    
    pd.testing.assert_frame_equal(left=test_residence_dist_data, right=file_residence_dist_data, check_exact=True)

def test_ede_df(testing_config_base):
    #test that the ede_df is correct
    model_run = ModelRun(testing_config_base)
    test_edes_data = model_run.demographic_edes
    file_name = testing_config_base.location + '.' + testing_config_base.config_name + '_edes.csv'
    file_edes_data = pd.read_csv(os.path.join(TESTING_RESULTS_DIR, file_name), index_col= 0)

    #round to rid floating point errors
    test_edes_data['y_EDE'] = test_edes_data['y_EDE'].round(9)
    test_edes_data['avg_dist'] = test_edes_data['avg_dist'].round(9)
    
    file_edes_data['y_EDE'] = file_edes_data['y_EDE'].round(9)
    file_edes_data['avg_dist'] = file_edes_data['avg_dist'].round(9)
    
    pd.testing.assert_frame_equal(left=test_edes_data, right=file_edes_data, check_exact=True)