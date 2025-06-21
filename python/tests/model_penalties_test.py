#pseudocode for tests for incorporate_penalties

#to test line 22:
    #check that lines 93 and 96 of model_run.py result in the same df
    #when run on testing_config_expanded

#to test that the penalty function as a whole is working as expected:
#Define:
#  result_no_school = output of incorporate_penlties on testing_config_expanded.yaml 
#  result_school_penalized = output of incorporate_penlties on testing_config_penalty.yaml
#  result_school = output of incorporate_penlties on testing_config_school.yaml
#  check that result_no_school.kp_factor.sum() <= result_school_penalized.kp_factor.sum() <= result_school.kp_factor_sum()
#NOTE: this only checks a property that should be true, not that the algorithm gives the correct value.

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

#to test that kp2 is correctly defined on line 57
#Define:
#  exclude_config = test_config_schools.yaml
#  penalize_config = test_config_pentalty.yaml
#run 
#  exclude_model = polling_model_factory(dist_df, alpha, exclude_config)
#  solve_model(exclude_model)
#  exclude_obj_value =  pyo.value(exclude_model.obj)
#  kp2 = the value of line 57 when run on penalize_config
#check that kp2 == exclude_obj_value

#test that kp2 > kp_pen > kp1 when run on test_config_pentalty.yaml
#kp_pen defined on line 97

#TODO:
# Should write a test for lines 80-93, but that requires coming up with example
# testing_locations_only.csv files that have the correct properties... let me think about this one.