'''Note that this testing framework pulls a (fixed) sample dataset from an existing county, runs the model on it, and checks
that the resulta are consistent. As such, this is a point check only, and not a proof of correctness'''

import math
import os

import pandas as pd
import pyomo.environ as pyo

from python.solver.model_config import PollingModelConfig
from python.solver import model_data, model_factory, model_solver

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TESTING_CONFIG_EXPANDED = os.path.join(TESTS_DIR, 'testing_config_expanded.yaml')

CONFIG = PollingModelConfig.load_config(TESTING_CONFIG_EXPANDED)
print(f'config -> {CONFIG}')
DIST_DF = model_data.clean_data(CONFIG, False, False)
TOTAL_POP = DIST_DF.groupby('id_orig')['population'].agg('unique').str[0].sum()
ALPHA_DF = model_data.clean_data(CONFIG, True, False)
ALPHA = model_data.alpha_min(ALPHA_DF)

MODEL = model_factory.polling_model_factory(DIST_DF, ALPHA, CONFIG)
model_solver.solve_model(MODEL, CONFIG.time_limit)

#Model and data characteristics
OPEN_PRECINCTS = {key for key in MODEL.open if MODEL.open[key].value ==1}
POTENTIAL_PRECINCTS = set(DIST_DF[DIST_DF.dest_type == 'potential'].id_dest)
OLD_POLLS = len(DIST_DF[DIST_DF.location_type == 'polling'])
ALL_RESIDENCES = set(DIST_DF.id_orig.unique())
MATCHED_RESIDENCES = {key[0] for key in MODEL.matching if MODEL.matching[key].value ==1}
MATCHED_PRECINCTS = {key[1] for key in MODEL.matching if MODEL.matching[key].value ==1}

def test_alpha_min():
    assert round(ALPHA, 11) ==  7.89213e-05 #value from R code

def test_kp_factor():
    DIST_DF['KP_factor'] = round(model_factory.compute_kp_factor(CONFIG, ALPHA, DIST_DF), 6)
    dist_df2 = DIST_DF[['id_orig', 'id_dest', 'KP_factor']]
    fixed_test_data = pd.read_csv('./test_kp_factor.csv') #data from R code
    fixed_test_data.kp_factor = round(fixed_test_data.kp_factor, 6)
    compare = dist_df2.merge(fixed_test_data, how = 'outer')
    assert compare.KP_factor.equals(compare.kp_factor)


#test model constraints
def test_open_constraint():
    #number of open precincts as described in config
    assert len(OPEN_PRECINCTS) == CONFIG.precincts_open


def test_max_new_constraint():
    #number of new precincts less than maxpctnew of number open
    new_precincts = POTENTIAL_PRECINCTS.intersection(OPEN_PRECINCTS)
    assert len(new_precincts) < CONFIG.maxpctnew* CONFIG.precincts_open


def test_min_old_constraint():
    #number of old precincts more than minpctold of old polls
    old_precincts = OPEN_PRECINCTS.difference(POTENTIAL_PRECINCTS)
    assert len(old_precincts) >= CONFIG.minpctold*OLD_POLLS


def test_res_assigned():
    #each residence assigned to exactly one precinct
    #Note: ignoring the radius calculation here
    assert MATCHED_RESIDENCES == ALL_RESIDENCES

def test_precinct_open():
    #residences matched to open precincts (and all open precincts matched)
    assert MATCHED_PRECINCTS == OPEN_PRECINCTS


def test_capacity():
    #each open precinct doesn't serve more that capacity * total pop / number open
    matching_list= [(key[0], key[1], MODEL.matching[key].value) for key in MODEL.matching if MODEL.matching[key].value ==1]
    matching_df = pd.DataFrame(matching_list, columns = ['id_orig', 'id_dest', 'matching'])

    #merge with dist_df
    result_df = pd.merge(DIST_DF, matching_df, on = ['id_orig', 'id_dest'])
    dest_pop_df = result_df[['id_dest', 'population']].groupby('id_dest').agg('sum')
    assert all(dest_pop_df.population <=(CONFIG.capacity*TOTAL_POP/CONFIG.precincts_open))

# Test the intermediate dataframe with driving distances
DRIVING_TESTING_CONFIG = os.path.join(TESTS_DIR, 'testing_config_driving.yaml')
DRIVING_CONFIG = PollingModelConfig.load_config(DRIVING_TESTING_CONFIG)
DRIVING_DIST_DF = model_data.clean_data(DRIVING_CONFIG, False, False)

# The test driving distances are exactly twice the haversine test distances
def test_driving_distances():
    assert DRIVING_DIST_DF['distance_m'].sum() == 2*DIST_DF['distance_m'].sum()
    # Test for penalty functionality
OBJ = pyo.value(MODEL.obj)
KP = -1/(CONFIG.beta*ALPHA)*math.log(OBJ)
TESTING_CONFIG_PENALTY = os.path.join(TESTS_DIR, 'testing_config_penalty.yaml')
PENALTY_CONFIG = PollingModelConfig.load_config(TESTING_CONFIG_PENALTY)
EX_MODEL = model_factory.polling_model_factory(DIST_DF, ALPHA, PENALTY_CONFIG, exclude_penalized_sites=True)
model_solver.solve_model(EX_MODEL, PENALTY_CONFIG.time_limit)
EX_OBJ = pyo.value(EX_MODEL.obj)
EX_KP = -1/(CONFIG.beta*ALPHA)*math.log(EX_OBJ) # same beta and alpha for both configs

def test_exclude_penalized():
    EX_OPEN_PRECINCTS = {key for key in EX_MODEL.open if EX_MODEL.open[key].value ==1}
    assert len(EX_OPEN_PRECINCTS - set(PENALTY_CONFIG.penalized_sites))==3

def test_penalized_model():
    penalty = (EX_KP - KP) / len(OPEN_PRECINCTS)
    PEN_MODEL = model_factory.polling_model_factory(DIST_DF, ALPHA, PENALTY_CONFIG,
                                                    exclude_penalized_sites=False,
                                                    site_penalty=penalty,
                                                    kp_penalty_parameter=KP)
    model_solver.solve_model(PEN_MODEL, PENALTY_CONFIG.time_limit)
    PEN_OPEN_PRECINCTS = {key for key in PEN_MODEL.open if PEN_MODEL.open[key].value ==1}
    PEN_OBJ = pyo.value(PEN_MODEL.obj)
    PEN_KP = -1/(CONFIG.beta*ALPHA)*math.log(PEN_OBJ) - penalty
    assert (PEN_KP > KP)
