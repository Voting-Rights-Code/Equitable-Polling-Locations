#from test_config_refactor import * #For testing only. Remove later 
import time
#from data_for_model import *
import pyomo.environ as pyo
from pyomo.opt import SolverStatus, TerminationCondition
import pandas as pd


def solve_model(model, time_limit):
    #define solver    
    solver_name = 'scip'
    solver = pyo.SolverFactory(solver_name)
    solver.options ={ 'limits/time':time_limit,  'limits/gap': 0.01, 'lp/threads':2 }
        
    results = solver.solve(model, tee=True)
    #solve_time = time.time() - start_time_0

    return results

