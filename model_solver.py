from test_config_refactor import * #For testing only. Remove later 
import time
#from data_for_model import *
import pyomo.environ as pyo
from pyomo.opt import SolverStatus, TerminationCondition
import pandas as pd


def solve_model(model, time_limit):

    #Pick a solver
    solver_name = 'scip'
    #solver_name = 'glpk'
    solver = pyo.SolverFactory(solver_name)
    if solver_name == 'cplex':
        solver.options['timelimit'] = time_limit
    elif solver_name == 'glpk':        
        solver.options['tmlim'] = time_limit
    elif solver_name == 'gurobi':          
        solver.options['TimeLimit'] = time_limit
    elif solver_name == 'scip':          
#        solver.options['limits/time'] = time_limit
         solver.options ={ 'limits/time':time_limit,  'limits/gap': 0.0001, 'lp/threads':2 }
        
    results = solver.solve(model, tee=True)
    solve_time = time.time() - start_time_0

    #print updates on status
    if ((results.solver.status == SolverStatus.ok) and
        (results.solver.termination_condition == TerminationCondition.optimal)):
        # Do something when the solution in optimal and feasible
        exit_status = 'Optimal'
        lower = results['Problem'][0]['Lower bound']
        upper = results['Problem'][0]['Upper bound']
        gap = abs(lower-upper)/abs(upper)
    elif ((results.solver.status == SolverStatus.ok) and #TODO:verify change
                                                         #when working with SCIP, reaching time limit results in status okay.
                                                         #previeous read: SolverStatus.aborted
          (results.solver.termination_condition == TerminationCondition.maxTimeLimit)):
        exit_status = 'Timed Out'
        lower = float(results['Problem'][0]['Lower bound'])
        upper = float(results['Problem'][0]['Upper bound'])
        gap = abs(lower-upper)/abs(upper)
    elif (results.solver.termination_condition == TerminationCondition.infeasible):
        print('Model Infeasible. Solve Time = ',solve_time)
        exit_status = 'infeasible'
        lower = 'none'
        upper = 'none'
        gap = 'infinite'
    else:
        print('Solver Status: ',  results.solver.status)

    solve_report = {'exit_status':exit_status, 'lower_bound':lower, 'upper_bound':upper,
                    'gap':gap, 'solve_time':solve_time}

    print(solve_report)

    if exit_status == 'Optimal':
        print(ea_model.obj())
    return results

