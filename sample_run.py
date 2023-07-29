
import test_config_refactor as config
from data_for_model import (clean_data, alpha_all, alpha_mean, alpha_min)
from model_factory import polling_model_factory
from model_solver import solve_model
from model_results import (incorporate_result,demographic_domain_summary, demographic_summary,write_results,)

#get main data frame
dist_df = clean_data(config.location, config.level, config.year)

#get alpha
alpha_df = clean_data(config.location, 'original', config.year)
    # TODO: (CR) I don't like having to call this twice like this. Need a better method
alpha  = alpha_min(alpha_df)

#build model
ea_model = polling_model_factory(dist_df, alpha, config)
print(f'model built. Solve for {config.time_limit} seconds')

#solve model
#TODO: (CR) this should probably be moved to a log file somewhere
result = solve_model(ea_model, config.time_limit)

#incorporate result into main dataframe
result_df = incorporate_result(dist_df, ea_model)

#calculate the average distances traveled by each demographic to the assigned precinct
demographic_prec = demographic_domain_summary(result_df, 'id_dest')

#calculate the average distances traveled by each demographic by residence
demographic_res = demographic_domain_summary(result_df, 'id_orig')

#calculate the average distances (and y_ede if beta !=0) traveled by each demographic
demographic_ede = demographic_summary(demographic_res, result_df,config.beta, alpha)

result_folder = f'{config.location}_result'
run_prefix = f'{config.location}_{config.year}_{config.level}_beta={config.beta}'
write_results(result_folder, run_prefix, result_df, demographic_prec, demographic_res, demographic_ede)

