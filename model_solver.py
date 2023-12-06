#######################################
#Created on 6 December 2023
#
#@author: Voting Rights Code
#@attribution: based off of code by Josh Murell
#######################################

''' Functions to solve models '''

import pyomo.environ as pyo

SOLVER_NAME = 'scip'
LIMITS_GAP = 0.01
LP_THREADS = 2

def solve_model(model, time_limit, log: bool=False, log_file_path=None):
    ''' This funciton will execute scip '''
    #define solver
    solver_name = SOLVER_NAME
    solver = pyo.SolverFactory(solver_name)
    solver.options ={ 'limits/time': time_limit,  'limits/gap': LIMITS_GAP, 'lp/threads': LP_THREADS }

    results = solver.solve(model, tee=log, logfile=log_file_path)

    return results

