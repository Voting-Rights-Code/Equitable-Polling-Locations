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


def test_alpha_min():
    assert round(alpha, 11) ==  7.239801e-05 #value from R code

def test_kp_factor():
    dist_df['KP_factor'] = round(model_factory.compute_kp_factor(config, alpha, dist_df), 6)
    dist_df2 = dist_df[['id_orig', 'id_dest', 'KP_factor']]
    fixed_test_data = pd.read_csv('tests/test_kp_factor.csv') #data from R code
    fixed_test_data.kp_factor = round(fixed_test_data.kp_factor, 6)
    compare = dist_df2.merge(fixed_test_data, how = 'outer')
    assert compare.KP_factor.equals(compare.kp_factor)


model = model_factory.polling_model_factory(dist_df, alpha, config)
model_solver.solve_model(model, config.time_limit)

open_precincts = {key for key in model.open if model.open[key].value ==1}
#test model constraints
def test_open_constraint():
    #number of open precincts as described in config
    assert len(open_precincts) == config.precincts_open

potential_precincts = set(dist_df[dist_df.dest_type == 'potential'].id_dest)

def test_max_new_constraint():
    #number of new precincts less than maxpctnew of number open
    new_precincts = potential_precincts.intersection(open_precincts)
    assert len(new_precincts) < config.maxpctnew* config.precincts_open

old_polls = len(dist_df[dist_df.location_type == 'polling'])

def test_min_old_constraint():
    #number of old precincts more than minpctold of old polls
    old_precincts = open_precincts.difference(potential_precincts)
    assert len(old_precincts) >= config.minpctold*old_polls

all_residences = set(dist_df.id_orig.unique())
matched_residences = {key[0] for key in model.matching if model.matching[key].value ==1}

def test_res_assigned():
    #each residence assigned to exactly one precinct 
    #Note: ignoring the radius calculation here
    assert matched_residences == all_residences

matched_precincts = {key[1] for key in model.matching if model.matching[key].value ==1}
def test_precinct_open():
    #residences matched to open precincts (and all open precincts matched)
    assert matched_precincts == open_precincts

total_pop = dist_df.groupby('id_orig')['population'].agg('unique').str[0].sum()

def test_capacity():
    #each open precinct doesn't serve more that capacity * total pop / number open
    matching_list= [(key[0], key[1], model.matching[key].value) for key in model.matching if model.matching[key].value ==1]
    matching_df = pd.DataFrame(matching_list, columns = ['id_orig', 'id_dest', 'matching'])

    #merge with dist_df
    result_df = pd.merge(dist_df, matching_df, on = ['id_orig', 'id_dest'])
    dest_pop_df = result_df[['id_dest', 'population']].groupby('id_dest').agg('sum')
    assert all(dest_pop_df.population <=(config.capacity*total_pop/config.precincts_open))

