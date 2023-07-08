import time
import math
from test_config_refactor import * #For testing only. Remove later 

from data_for_model import (
    #add_weight_factors,
    clean_data,
    get_max_min_dist,
    alpha_all,
    alpha_min,
    alpha_mean
    #precinct_res_pairings,
    #res_precinct_pairings,
)

import pyomo.environ as pyo
from pyomo.opt import SolverStatus, TerminationCondition
import pandas as pd




start_time_0 = time.time()
def build_model(beta = beta, max_min_mult = max_min_mult, maxpctnew = maxpctnew, precincts_open = precincts_open):
    ######## get data and set parameters #######
    dist_df = clean_data(location, level, year)
    alpha_df = clean_data(location, 'original', year)
    alpha  = alpha_all(alpha_df)
    global_max_min_dist = get_max_min_dist(dist_df)
    max_min = max_min_mult * global_max_min_dist
    precincts_open = len(set(dist_df[dist_df['dest_type']=='polling']['id_dest']))

    ####set model to be concrete####
    model = pyo.ConcreteModel()

    ####define constants####
    #total population
    total_pop = dist_df.groupby('id_orig')['population'].agg('mean').sum() #TODO: Check that this is unique as desired.
    

    ####define model simple indices####
    #all possible precinct locations (unique)
    model.precincts = pyo.Set(initialize = list(set(dist_df['id_dest'])))
    #all possible residence locations with population > 0 (unique)
    model.residences = pyo.Set(initialize = list(set(dist_df['id_orig'])))
    #residence, precint pairs
    model.pairs = model.residences * model.precincts 
    

    ####define model parameters####
    #Populations of residences
    model.population = pyo.Param(model.residences, initialize =dist_df.groupby('id_orig')['population'].agg('mean'))
    #Precinct residence distances
    model.distance = pyo.Param(model.pairs, initialize = dist_df[['id_orig', 'id_dest', 'distance_m']].set_index(['id_orig', 'id_dest']))
    #population weighted distances
    model.weighted_dist = pyo.Param(model.pairs, initialize = dist_df[['id_orig', 'id_dest', 'Weighted_dist']].set_index(['id_orig', 'id_dest']))
    
    #KP factor 
    dist_df['KP_factor'] = math.e**(-beta*alpha*dist_df['distance_m'])
    model.KP_factor = pyo.Param(model.pairs, initialize = dist_df[['id_orig', 'id_dest', 'KP_factor']].set_index(['id_orig', 'id_dest']))
    #new location marker
    dist_df['new_location'] = 0
    dist_df['new_location'].mask(dist_df['dest_type']!='polling', 1, inplace = True)

    model.new_locations = pyo.Param(model.precincts, initialize = dist_df[['id_dest', 'new_location']].drop_duplicates().set_index(['id_dest']))

    ####define model variables####  TODO:(SA) identify if variable or param  
    model.matching = pyo.Var(model.pairs, domain=pyo.Binary )
    model.open = pyo.Var(model.precincts, domain=pyo.Binary )

    ####define parameter dependent indices####
    #precinct in residence radius
    model.within_residence_radius = pyo.Set(model.residences, initialize = {res:[prec for prec in model.precincts if model.distance[(res,prec)] <= max_min] for res in model.residences})
    #residences in precint radius    
    model.within_precinct_radius = pyo.Set(model.precincts, initialize = {prec:[res for res in model.residences if model.distance[(res,prec)] <= max_min] for prec in model.precincts})
    start_time_1 = time.time()
    print(f'constants defined in {start_time_1 - start_time_0} seconds')
    
    ####define objective functions####
    def obj_rule_0(model):
        #take average populated weighted distance
        average_weighted_distances = sum(model.matching[pair]* model.weighted_dist[pair] for pair in model.pairs)/total_pop
        return (average_weighted_distances)
    def obj_rule_not_0(model):
        #take average by kp factor weight
        #pair[0] = residence
        average_weighted_distances = sum(model.population[pair[0]]* model.matching[pair]* model.KP_factor[pair] for pair in model.pairs)/total_pop
        return (average_weighted_distances)
    if beta== 0:
        model.obj = pyo.Objective(rule=obj_rule_0, sense=pyo.minimize)
    if beta!= 0:
        model.obj = pyo.Objective(rule=obj_rule_not_0, sense=pyo.minimize)
    start_time_2 = time.time()
    print(f'Objective functions defined in {start_time_2 - start_time_1} seconds')
    
    ####define constraints####
    print(f'Define constraints')
    #Open precincts constraint.
    def open_rule(model): 
        return sum(model.open[precinct] for precinct in model.precincts) == precincts_open
    model.open_constraint = pyo.Constraint(rule=open_rule)
    start_time_3 = time.time()
    print(f'Number of precints contraint built in {start_time_3 - start_time_2} seconds')

    #percent of new open precincts not to exceed maxpctnew
    def max_new_rule(model):
        return sum(model.open[precinct]* model.new_locations[precinct] for precinct in model.precincts) <= maxpctnew*precincts_open
    model.max_new_constraint = pyo.Constraint(rule=max_new_rule)
    start_time_4 = time.time()
    print(f'Max new locations contraint built in {start_time_4 - start_time_3} seconds')

    #assigns each census block to a single precinct in its neighborhood 
    def res_assigned_rule(model, residence):
        return (sum(model.matching[residence, precinct] for precinct in model.within_residence_radius[residence]) == 1)
    model.res_assigned_constraint = pyo.Constraint(model.residences, rule=res_assigned_rule)
    start_time_5 = time.time()
    print(f'Single precinct contraint built in {start_time_5 - start_time_4} seconds')
    
    #residences can only be covered by precincts that are opened
    #print(f"Defining assigning residents to only open precincts constraint.")
    def precinct_open_rule(model, res,prec):
        return (model.matching[res,prec]<= model.open[prec])
    model.precinct_open_constraint = pyo.Constraint(model.pairs, rule=precinct_open_rule)
    start_time_6 = time.time()
    print(f'Open precinct constraint defined in built in {start_time_6 - start_time_5} seconds')

    #respects capacity limits and prevents overcrowding by restricting the number that can go to a precinct to some scaling factor of the avg population per center
    def capacity_rule(model,prec):
        return (sum(model.population[res]*model.matching[res,prec] for res in model.within_precinct_radius[prec])<=(capacity*total_pop/precincts_open))
    model.capacity_constraint = pyo.Constraint(model.precincts, rule=capacity_rule)
    start_time_7 = time.time()
    print(f'Capacity constraint defined in built in {start_time_7 - start_time_6} seconds')
    print(f'Model built in {start_time_7 - start_time_0}')
    #model.obj.pprint()
    return model


def solve_model(model, time_limit = time_limit):
   
    start_time_0 = time.time()
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

####################

ea_model = build_model()
print(f'model built. Solve for {time_limit} seconds')

ea_result = solve_model(ea_model, time_limit)