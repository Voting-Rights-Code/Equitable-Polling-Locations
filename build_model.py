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

####constants####
#alpha = alpha_def(basedist) #NOTE: No longer needed. part of dist_df def
global_max_min_dist = get_max_min_dist(dist_df)


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
    #NOTE: As currently written, assumes dist_df has no duplicates
    
    '''#list of all possible precinct locations (unique)
    precincts = list(set(dist_df['id_dest']))
    ##list of all possible residence locations with population > 0 (unique)
    residences = list(set(dist_df['id_orig']))
    #list of residence, precint pairs
    residence_precinct_pairs = list(zip(dist_df.id_orig, dist_df.id_dest)) 
    #population dictionary
    pop_dict = dist_df.groupby('id_orig')['population'].agg('mean').to_dict()
    #dictionary: {precinct:[list of residences in area]}
    residences_in_radius_of_precinct = precinct_res_pairings(max_min, dist_df)
    #dictionary: {residence:[list of precincts in area]}
    precincts_in_radius_of_residence = res_precinct_pairings(max_min, dist_df)'''

    ####define constants####
    #total population
    total_pop = dist_df.groupby('id_orig')['population'].agg('mean').sum() #TODO: Check that this is unique as desired.
    alpha  = alpha_SA(dist_df)

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
    dist_df['KP_factor'] = math.e**(-beta*alpha*dist_df['Weighted_dist'])
    model.KP_factor = pyo.Param(model.pairs, initialize = dist_df[['id_orig', 'id_dest', 'KP_factor']].set_index(['id_orig', 'id_dest']))
    #new location marker
    dist_df['new_location'] = 0
    dist_df['new_location'].mask(dist_df['dest_type']!='polling', 1, inplace = True)

    model.new_locations = pyo.Param(model.precincts, initialize = dist_df[['id_dest', 'new_location']].drop_duplicates().set_index(['id_dest']))

    ####define model variables####  TODO:(SA) identify if variable or param  
    model.matching = pyo.Var(model.pairs, domain=pyo.Binary )
    model.open = pyo.Var(model.precincts, domain=pyo.Binary )

    ####define parameter dependent indices####
    #residences in precint radius
    model.within_residence_radius = pyo.Set(model.residences, initialize = {res:[prec for prec in model.precincts if model.distance[(res,prec)] <= max_min] for res in model.residences})
    #precinct in residence radius
    model.within_precinct_radius = pyo.Set(model.precincts, initialize = {prec:[res for res in model.residences if model.distance[(res,prec)] <= max_min] for prec in model.precincts})
    start_time_1 = time.time()
    print(f'constants defined in {start_time_1 - start_time_0} seconds')
    
    ####define objective function####
    def obj_rule(model):
        if beta == 0:
            weight_dict = model.weighted_dist
        else: #(beta != 0)
            weight_dict = model.KP_factor
        #take average by appropriate weight
        average_weighted_distances = sum(model.matching[pair]* weight_dict[pair] for pair in model.pairs)/total_pop
        return (average_weighted_distances)
    
    # def obj_rule_SA(model): #NOTE: will not work due to non-linearities.
    #     #TODO: (SA, DS) This will slow things down, but is it correct?
    #     if beta == 0:
    #         return(sum(model.weighted_dist[pair] *model.matching[pair] for pair in model.pairs)/total_pop)
    #     else: #(beta != 0)
    #         #define weighted distances
    #         numerator = sum(model.weighted_dist[pair] *model.matching[pair] for pair in model.pairs)
    #         #define weighted distances squared
    #         denominator = sum((model.weighted_dist[pair] * model.distance[pair]*model.matching[pair]) for pair in model.pairs)
    #         #this should give the quantity in the square brackes in (2) of Josh's paper
    #         average_weighted_distances = (math.e**(-sum(beta*numerator/denominator*model.weighted_dist[pair] *model.matching[pair] for pair in model.pairs)))/total_pop
    #         return(average_weighted_distances)

    model.obj = pyo.Objective(rule=obj_rule, sense=pyo.minimize)
    start_time_2 = time.time()
    print(f'Objective functions defined in {start_time_2 - start_time_1} seconds')
    breakpoint()
    ####define constraints####
    print(f'Define constraints')
    #Open precincts constraint.
    def open_rule(model): 
        return sum(model.open[precinct] for precinct in model.precincts) == precincts_open
    model.open_constraint = pyo.Constraint(rule=open_rule)
    start_time_3 = time.time()
    print(f'Number of precints contraint built in {start_time_3 - start_time_2} seconds')

    #percent of new open precincts not to exceed maxpctnew
    def max_new(model):
        return sum(model.open[precinct]* model.new_locations[precinct] for precinct in model.precincts) <= maxpctnew*precincts_open
    model.max_new_constraint = pyo.Constraint(rule=max_new)
    start_time_4 = time.time()
    print(f'Max new locations contraint built in {start_time_4 - start_time_3} seconds')

    #assigns each census block to a single precinct in its neighborhood 
    def res_assigned_rule(model, residence):
        return (sum(model.open[precinct] for precinct in model.within_residence_radius[residence]) == 1)
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
    breakpoint()
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