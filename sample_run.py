import test_config_refactor as config
from model_factory import polling_model_factory
from model_solver import solve_model

ea_model = polling_model_factory(config)
print(f'model built. Solve for {config.time_limit} seconds')
result = solve_model(ea_model, config.time_limit)
