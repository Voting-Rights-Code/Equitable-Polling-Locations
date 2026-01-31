''' Tests for working with penalties '''

# pylint: disable=protected-access,function-redefined

import pandas as pd
import pyomo.environ as pyo

from python.solver.model_run import ModelRun
from python.solver import model_solver
from python.solver import model_penalties
from python.solver.model_penalties import PenalizeModel
from python.solver.model_results import incorporate_result


def test_penalty_selection_false(testing_config_penalty_unused):
    #testing that the penality function works correctly when no penalized sites are MOT chosen
    penalty_run_setup = ModelRun(testing_config_penalty_unused).run_setup
    # penalty_run_setup = model_run.prepare_run(testing_config_penalty_unused)
    model_solver.solve_model(penalty_run_setup.ea_model, testing_config_penalty_unused.time_limit, limits_gap=0.0)
    penalty_result_df = incorporate_result(
        penalty_run_setup.dist_df,
        penalty_run_setup.ea_model,
        testing_config_penalty_unused.log_distance,
    )

    penalty_model = PenalizeModel(penalty_run_setup, penalty_result_df)
    penalty_model.run()
    assert not penalty_model.penalized_selections


def test_penalty_selection_true(testing_config_penalty):
    #testing that the penality function works correctly when no penalized sites are chosen
    penalty_run_setup = ModelRun(testing_config_penalty).run_setup
    # penalty_run_setup = model_run.prepare_run(testing_config_penalty)
    model_solver.solve_model(penalty_run_setup.ea_model, testing_config_penalty.time_limit, limits_gap=0.0)
    penalty_result_df = incorporate_result(
        penalty_run_setup.dist_df,
        penalty_run_setup.ea_model,
        testing_config_penalty.log_distance,
    )

    penalty_model = PenalizeModel(penalty_run_setup, penalty_result_df)
    penalty_model.run()
    assert len(penalty_model.penalized_selections) == 2

def test_kp1(testing_config_keep, testing_config_penalty):
    #get kp value from the keep_config using model_run machinery
    keep_run_setup = ModelRun(testing_config_keep).run_setup
    # keep_run_setup = model_run.prepare_run(testing_config_keep)
    model_solver.solve_model(keep_run_setup.ea_model, testing_config_keep.time_limit, limits_gap=0.0)
    #keep_result_df = incorporate_result(keep_run_setup.dist_df, keep_run_setup.ea_model)
    keep_obj_value = pyo.value(keep_run_setup.ea_model.obj)
    keep_kp = model_penalties.compute_kp(testing_config_keep, keep_run_setup.alpha, keep_obj_value)

    #get kp1 value from the penalize_config using penalty machinery
    penalty_run_setup = ModelRun(testing_config_penalty).run_setup
    # penalty_run_setup = model_run.prepare_run(testing_config_penalty)
    model_solver.solve_model(penalty_run_setup.ea_model, testing_config_penalty.time_limit, limits_gap=0.0)
    penalty_result_df = incorporate_result(
        penalty_run_setup.dist_df,
        penalty_run_setup.ea_model,
        testing_config_penalty.log_distance,
    )

    penalty_model = PenalizeModel(penalty_run_setup, penalty_result_df)
    penalty_model.run()
    #penalty_penalize_model._compute_kp1()
    assert penalty_model.kp1 == keep_kp


def test_kp2(testing_config_exclude, testing_config_penalty):
    #get kp value from the exclue_config using model_run machinery
    exclude_run_setup = ModelRun(testing_config_exclude).run_setup
    # exclude_run_setup = model_run.prepare_run(testing_config_exclude)
    model_solver.solve_model(exclude_run_setup.ea_model, testing_config_exclude.time_limit, limits_gap=0.0)
    #keep_result_df = incorporate_result(keep_run_setup.dist_df, keep_run_setup.ea_model)
    exclude_obj_value = pyo.value(exclude_run_setup.ea_model.obj)
    exclude_kp = model_penalties.compute_kp(testing_config_exclude, exclude_run_setup.alpha, exclude_obj_value)

    #get kp2 value from the penalize_config using penalty machinery
    penalty_run_setup = ModelRun(testing_config_penalty).run_setup
    # penalty_run_setup = model_run.prepare_run(testing_config_penalty)
    model_solver.solve_model(penalty_run_setup.ea_model, testing_config_penalty.time_limit, limits_gap=0.0)
    penalty_result_df = incorporate_result(
        penalty_run_setup.dist_df,
        penalty_run_setup.ea_model,
        testing_config_penalty.log_distance,
    )

    penalty_model = PenalizeModel(penalty_run_setup, penalty_result_df)
    penalty_model.run()
    assert penalty_model.kp2 == exclude_kp


def test_kp_inequalities(testing_config_penalty):
#test that kp2 > kp_pen > kp1 when run on test_config_pentalty.yaml
#kp_pen defined on line 97
    penalty_run_setup = ModelRun(testing_config_penalty).run_setup
    # penalty_run_setup = model_run.prepare_run(testing_config_penalty)
    model_solver.solve_model(penalty_run_setup.ea_model, testing_config_penalty.time_limit, testing_config_penalty.limits_gap)
    penalty_result_df = incorporate_result(
        penalty_run_setup.dist_df,
        penalty_run_setup.ea_model,
        testing_config_penalty.log_distance,
    )

    penalty_model = PenalizeModel(penalty_run_setup, penalty_result_df)
    penalty_model.run()
    assert penalty_model.kp2 > penalty_model.kp_pen
    assert penalty_model.kp_pen > penalty_model.kp1


    # model_run = ModelRun(testing_config_penalty, True)
    # penalize_model = model_run._penalize_model
    # print(penalize_model._run_setup.config)
    # config = penalize_model._run_setup.config


    # initial_result_df_hash = pd.util.hash_pandas_object(model_run._initial_result_df).sum()
    # print('\n\n\n\n\n')
    # print(f'test_kp_inequalities result_df hash: {initial_result_df_hash}')

    # # print(model_run._initial_result_df.head())

    # # .PollingModelConfig(config_name='testing_config_penalty', config_set='testing', location='testing', year=['2020', '2022'], bad_types=['bg_centroid'], beta=-2, time_limit=360000, census_year=2020, precincts_open=3, maxpctnew=1, minpctold=0.5, max_min_mult=5, capacity=5, fixed_capacity_site_number=None, driving=False, penalized_sites=['College Campus - Potential', 'Fire Station - Potential'], log_distance=False, commit_hash=None, run_time=None, config_file_path='/Users/abditus/src/Voting-Rights-Code/Equitable-Polling-Locations/datasets/configs/testing/testing_config_penalty.yaml', log_file_path=None, db_id=None, data_source='csv', map_source_date=None, environment=None)
    # assert config.config_name == 'testing_config_penalty'
    # assert config.location == 'testing'
    # assert config.census_year == 2020
    # assert config.driving is False
    # assert config.penalized_sites == ['College Campus - Potential', 'Fire Station - Potential']
    # assert config.log_distance is False
    # assert config.time_limit == 360000
    # assert config.beta == -2
    # assert config.precincts_open == 3
    # assert config.maxpctnew == 1
    # assert config.minpctold == 0.5
    # assert config.max_min_mult == 5
    # assert config.capacity == 5
    # assert config.fixed_capacity_site_number is None
    # assert config.bad_types == ['bg_centroid']
    # assert config.year == ['2020', '2022']

    # penalize_model.run()
    # dist_df_hash = pd.util.hash_pandas_object(penalize_model._run_setup.dist_df).sum()
    # print(f'test_kp_inequalities dist_df hash: {dist_df_hash}')
    # print(f'alpha: {penalize_model._run_setup.alpha}')
    # print(f'_ea_model_obj_value: {penalize_model._ea_model_obj_value}')
    # print(f'_ea_model_penalized_obj_value: {penalize_model._ea_model_penalized_obj_value}')
    # print(f'_ea_model_exclusions_obj_value: {penalize_model._ea_model_exclusions_obj_value}')
    # print('-------------------------------------\n\n\n\n\n')

    # assert initial_result_df_hash == -2763798977526733105
    # assert dist_df_hash == -951405256011063288
    # assert penalize_model._run_setup.alpha == 7.992335106131607e-05

    # assert penalize_model.kp2 > penalize_model.kp_pen
    # assert penalize_model.kp_pen > penalize_model.kp1



def test_final_statistics(testing_config_penalty):
    #fixes the values from logs\20250718113608_testing_config_penalty.yaml.penalty.log
    #assuming that this version is correctly implemented

    model_run = ModelRun(testing_config_penalty)

    hash_val = pd.util.hash_pandas_object(model_run._initial_result_df).sum()
    print('\n\n\n\n\n')
    print(f'test_final_statistics result_df hash: {hash_val}')


    penalty_run_setup = model_run.run_setup
    # penalty_run_setup = model_run.prepare_run(testing_config_penalty)
    model_solver.solve_model(penalty_run_setup.ea_model, testing_config_penalty.time_limit, limits_gap=0.0)
    penalty_result_df = incorporate_result(
        penalty_run_setup.dist_df,
        penalty_run_setup.ea_model,
        testing_config_penalty.log_distance,
    )
    hash_val = pd.util.hash_pandas_object(penalty_result_df).sum()
    print(f'test_final_statistics penalty_result_df hash: {hash_val}')
    print('-------------------------------------\n\n\n\n\n')
    penalty_model = PenalizeModel(penalty_run_setup, penalty_result_df)
    penalty_model.run()
    assert round(penalty_model.kp_pen, 2) ==  6243.37
    assert round(penalty_model.optimal_kp, 2) == 5945.84
    assert round(penalty_model.kp1, 2) == 5723.48
    assert round(penalty_model.kp2, 2) == 6339.56
    assert round(penalty_model.penalty, 2) == 308.04
