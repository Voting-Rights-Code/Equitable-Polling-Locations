from test_config_refactor import * #For testing only. Remove later 
import time
from data_for_model import *
import pyomo.environ as pyo
from pyomo.opt import SolverStatus, TerminationCondition
import pandas as pd


#####################################
#Get key data frames and constants
#####################################

####dataframes####
#TODO: Check if really both of these are needed
basedist = get_base_dist(location, year)
dist_df = get_dist_df(basedist, level, year)
dist_df = add_weight_factors(basedist, dist_df, beta)

####constants####
#alpha = alpha_def(basedist) #NOTE: No longer needed. part of dist_df def
global_max_min_dist = get_max_min_dist(basedist)


#check if poll number has been assigned in config
#if not, give it the default number of polls in the file
poll_number_exists = 'precincts_open' in  globals() or 'precincts_open' in  locals()
if not poll_number_exists:
    #Set it to the number of polling locations in the data
    precincts_open = len(set(dist_df[dist_df['dest_type']=='polling']['id_dest']))
max_min_multiplier_exists = 'max_min_mult' in  globals() or 'neighborhood_dist' in  locals()
if not max_min_multiplier_exists:
    #set to global_max_min_dist if not user provided
    max_min = global_max_min_dist
else: 
    max_min = max_min_mult * global_max_min_dist #TODO (CR): lines 31-35 is setting a scalar
                                                 # multiplier to global_max_min_dist
                                                 # this should default to 1, unless the user wants
                                                 # a different value.
max_pct_exists = 'maxpctnew' in  globals() or 'maxpctnew' in  locals()
if not maxpctnew:
    #set to max percent new to all.
    maxpctnew = 1

start_time_0 = time.time()
def build_model(dist_df = dist_df, beta = beta, max_min = max_min, maxpctnew = maxpctnew, precincts_open = precincts_open):
    ####set model to be concrete####
    model = pyo.ConcreteModel()

    ####define necessary lists and dictionaries####
    #NOTE: As currently written, assumes dist_df has not duplicates
    
    #list of all possible precinct locations (unique)
    precincts = list(set(dist_df['id_dest']))
    ##list of all possible residence locations with population > 0 (unique)
    residences = list(set(dist_df['id_orig']))
    #list of residence, precint pairs
    residence_precinct_pairs = list(zip(dist_df.id_orig, dist_df.id_dest)) 
    #population dictionary
    pop_dict = dist_df.groupby('id_orig')['population'].agg('mean').to_frame().reset_index().set_index('id_orig')['population'].to_dict()
    #dictionary: {precinct:[list of residences in area]}
    residences_in_radius_of_precinct = precinct_res_pairings(max_min, dist_df)

    ####define model constants####
    #total population
    total_pop = dist_df.groupby('id_orig')['population'].agg('mean').sum() #TODO: Check that this is unique as desired.

    ####define model variables####
    model.x = pyo.Var(precincts, domain=pyo.Binary)
    model.z = pyo.Var(residence_precinct_pairs, domain=pyo.Binary)
    
    start_time_1 = time.time()
    print(f'constants defined in {start_time_1 - start_time_0} seconds')

    ####define objective function####
    def obj_rule(model):
        if beta == 0:
            weighting_column = 'Weighted_dist'
        else: #(beta != 0)
            weighting_column = 'KP_factor'
        #merge model var values to dist_df
        df = dist_df.copy()
        #TODO: (SA) CANNOT PUT MODEL.FOO.VALUE INTO A DATAFRAME 
        model_value_list = [[resident_id, precinct_id, model.x[precinct_id].value, model.z[resident_id, precinct_id].value] 
                            for resident_id, precinct_id in residence_precinct_pairs]
        model_df = pd.DataFrame(model_value_list, columns = ['id_orig', 'id_dest', 'model.x', 'model.z'])
        df = df.merge(model_df, how = 'left', on = ['id_orig', 'id_dest'])
        df['Weighted_distances'] = df[weighting_column] * df['model.z']
        #take average
        average_weighted_distances = sum((1/total_pop)*df['Weighted_distances'])
        return (average_weighted_distances)
    model.obj = pyo.Objective(rule=obj_rule, sense=pyo.minimize)
    start_time_2 = time.time()
    print(f'Objective function defined in {start_time_2 - start_time_1} seconds')
    
    ####define constraints####
    print(f'Define constraints')
    #Open precincts constraint.
    def open_rule(model): 
        return sum(model.x[precint_id] for precint_id in precincts) == precincts_open
    model.open_constraint = pyo.Constraint(rule=open_rule)
    start_time_3 = time.time()
    print(f'Number of precints contraint built in {start_time_3 - start_time_2} seconds')

    #percent of new precincts not to exceed maxpctnew
    new_locations = list(set(dist_df[(dist_df['dest_type']!='polling')]['id_dest']))
    def max_new(model):
        return sum(model.x[precint_id] for precint_id in new_locations) <= maxpctnew*precincts_open
    model.max_new_constraint = pyo.Constraint(rule=max_new)
    start_time_4 = time.time()
    print(f'Max new locations contraint built in {start_time_4 - start_time_3} seconds')

    #assigns each census block to a single precinct in its neighborhood
    precincts_in_radius_of_residence = res_precinct_pairings(max_min, dist_df) 
    def res_assigned_rule(model, residence_id):
        return (sum(model.z[residence_id,precinct_id] for precinct_id in precincts_in_radius_of_residence[residence_id]) == 1)
    model.res_assigned_constraint = pyo.Constraint(residences, rule=res_assigned_rule)
    start_time_5 = time.time()
    print(f'Single precinct contraint built in {start_time_5 - start_time_4} seconds')
    
    #residences can only be covered by precincts that are opened
    #print(f"Defining assigning residents to only open precincts constraint.")
    def precinct_open_rule(model,residence_id,precint_id):
        return (model.z[residence_id,precint_id]<= model.x[precint_id])
    model.precinct_open_constraint = pyo.Constraint(residence_precinct_pairs, rule=precinct_open_rule)
    start_time_6 = time.time()
    print(f'Open precinct constraint defined in built in {start_time_6 - start_time_5} seconds')

    #respects capacity limits and prevents overcrowding by restricting the number that can go to a precinct to some scaling factor of the avg population per center
    def capacity_rule(model,precinct_id):
        return (sum(pop_dict[residence_id]*model.z[residence_id,precinct_id] for residence_id  in residences_in_radius_of_precinct[precinct_id])<=(capacity*total_pop/precincts_open))
    model.capacity_constraint = pyo.Constraint(precincts, rule=capacity_rule)
    start_time_7 = time.time()
    print(f'Capacity constraint defined in built in {start_time_7 - start_time_6} seconds')
    print(f'Model built in {start_time_7 - start_time_0}')

    model.obj.pprint()
    return model


def solve_model(model, time_limit = time_limit):
   

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
    return(results)

####################
ea_model = build_model()
print(f'model built. Solve for {time_limit} seconds')

ea_result = solve_model(ea_model)