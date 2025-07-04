''' Tests for working with penalties '''

import pandas.testing as pd_testing

import pyomo.environ as pyo

from python.solver import model_factory, model_run
from python.solver import model_solver
from python.solver import model_penalties
from python.solver.model_config import PollingModelConfig
from python.solver.model_penalties import incorporate_penalties
from python.solver.model_results import incorporate_result
from python.solver.model_solver import solve_model

def test_incorperate_results_and_penalties(testing_config_expanded: PollingModelConfig):
    '''
    Confirm that incorporate_result and incorporate_penalties produce the same results on testing_config_expanded.
    '''
    #to test line 22:
    #check that lines 93 and 96 of model_run.py result in the same df
    #when run on testing_config_expanded

    config = testing_config_expanded
    run_setup = model_run.prepare_run(config, False)

    solve_model(run_setup.ea_model, config.time_limit, log=False, log_file_path=config.log_file_path)

    incorporate_result_df = incorporate_result(run_setup.dist_df, run_setup.ea_model)

    incorporate_penalties_df = incorporate_penalties(
        run_setup.dist_df,
        run_setup.alpha,
        run_setup.run_prefix,
        incorporate_result_df,
        run_setup.ea_model,
        config,
        False,
    )

    pd_testing.assert_frame_equal(
        incorporate_result_df,
        incorporate_penalties_df,
        check_like=True,
    )

def test_incorporate_penalties(result_no_school_df, result_school_penalized_df, result_school_df):
    ''' NOTE: this only checks a property that should be true, not that the algorithm gives the correct value '''
    result_no_school_kp_factor_sum = result_no_school_df.KP_factor.sum()
    result_school_penalized_kp_factor_sum = result_school_penalized_df.KP_factor.sum()
    result_school_kp_factor_sum = result_school_df.KP_factor.sum()

    print(result_no_school_kp_factor_sum)
    print(result_school_penalized_kp_factor_sum)
    print(result_school_kp_factor_sum)

    assert result_no_school_kp_factor_sum <= result_school_penalized_kp_factor_sum
    assert result_school_penalized_kp_factor_sum <= result_school_kp_factor_sum

def test_kp1(testing_config_schools, testing_config_penalty, distances_df, alpha_min):
    #to test that kp1 is correctly defined on line 43
    #Define:
    #  keep_config = test_config_schools.yaml
    #  penalize_config = test_config_pentalty.yaml
    #run
    #  keep_model = polling_model_factory(dist_df, alpha, keep_config)
    #  solve_model(keep_model)
    #  keep_obj_value =  pyo.value(keep_model.obj)
    #  kp1 = the value of line 43 when run on penalize_config
    #check that kp1 == keep_obj_value

    keep_config = testing_config_schools
    penalize_config = testing_config_penalty

    keep_model = model_factory.polling_model_factory(distances_df, alpha_min, keep_config)
    model_solver.solve_model(keep_model, keep_config.time_limit)
    keep_obj_value = pyo.value(keep_model.obj)

    penalize_model = model_factory.polling_model_factory(distances_df, alpha_min, penalize_config)
    model_solver.solve_model(penalize_model, penalize_config.time_limit)
    penalize_obj_value = pyo.value(penalize_model.obj)

    kp1 = model_penalties.compute_kp(penalize_config, alpha_min, penalize_obj_value)
    keep_kp = model_penalties.compute_kp(keep_config, alpha_min, keep_obj_value)

    assert kp1 == keep_kp

def test_kp2(testing_config_expanded, testing_config_penalty, distances_df, alpha_min):
    #to test that kp2 is correctly defined on line 57
    #Define:
    #  exclude_config = test_config_expanded.yaml
    #  penalize_config = test_config_pentalty.yaml
    #run
    #  exclude_model = polling_model_factory(dist_df, alpha, exclude_config)
    #  solve_model(exclude_model)
    #  exclude_obj_value =  pyo.value(exclude_model.obj)
    #  kp2 = the value of line 57 when run on penalize_config
    #check that kp2 == exclude_obj_value

    exclude_config = testing_config_expanded
    penalize_config = testing_config_penalty

    exclude_model = model_factory.polling_model_factory(distances_df, alpha_min, exclude_config)
    model_solver.solve_model(exclude_model, exclude_config.time_limit)
    exclude_obj_value = pyo.value(exclude_model.obj)

    penalize_model = model_factory.polling_model_factory(distances_df, alpha_min, penalize_config, exclude_penalized_sites=True)
    model_solver.solve_model(penalize_model, penalize_config.time_limit)
    penalize_obj_value = pyo.value(penalize_model.obj)

    kp2 = model_penalties.compute_kp(penalize_config, alpha_min, penalize_obj_value)
    exclude_kp = model_penalties.compute_kp(exclude_config, alpha_min, exclude_obj_value)

    assert kp2 == exclude_kp




#test that kp2 > kp_pen > kp1 when run on test_config_pentalty.yaml
#kp_pen defined on line 97

#TODO:
# Should write a test for lines 80-93, but that requires coming up with example
# testing_locations_only.csv files that have the correct properties... let me think about this one.