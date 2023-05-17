"""
Created on Wed 17 Oct 2021

@author: murrell  
updated by skipper 1 Oct 2022

This module builds an integer program optimization model and exports the resulting statistics.

Functions:
    optimize(CITY, YEAR, LEVEL, BETA, BETAZERO=-2, MAXPCTNEW=1, time_limit=28800, out_path="results\\")
    equal_access()
    get_results_df()
    get_precinct_pop_df()
    get_average_distance
    get_EDE
    get_demographic_EDE()
    get_averagevariance()
    get_EDE_variance()
    get_EDE_deviation()
    export_data()
"""
#read in modules
import pandas as pd
import pyomo.environ as pyo
import math
import statistics
from pyomo.opt import SolverStatus, TerminationCondition
import time

#import programs
import get_data as gd

#defining the model
def equal_access(residences, precincts, pop_dict, pop_demographics, neighborhood_dict, res_precinct_pairings, precinct_res_pairings, city, beta, betazero, alpha,capacity, precincts_open, demographic, new_locations, maxpctnew):
    """
    Build a model to offer a more equitable distribution of polling places.
    
    Keyword arguments:
    residences -- ID code for the residents in the a given census block
    precincts -- ID for all possible voting precincts locations
    pop_dict -- Dictionary of residences as keys and respective populations as values
    pop_demographics -- Dictionary of the residences as keys and population of a demographic as values
    neighborhood_dict -- Dictionary of census blocks (keys) and the precincts (list of values) within ____ meters
    res_precinct_pairings -- the set of precincts in the neighborhood of a residence
    precinct_res_pairings -- the set of residences in the neighborhood of a precinct
    city -- city of interest
    beta -- beta value (between 0 and -2)
    betazero -- placeholder value for beta if the user desires to optimize for average distance vice EDE
    alpha -- the alpha value for the distribution of distances
    capacity -- scaling factor for average number of people per polling location
    precincts_open -- the number of precincts opened in the specficied city and respective year
    demographic -- demographic of interest
    new_locations -- ID for potential *new* voting precincts (default is empty list -- makes no difference)
    pctmaxnew -- (decimal) percent of locations that can be changed; default is 1 (100% can be changed)

    
    
    Return:
    Pyomo model
    """
    total_pop=sum(pop_dict.values())
    
    #concrete pyomo model
    model = pyo.ConcreteModel()
    print(f"Starting to generate variables.")
    #binary variables that correspond to the assignment status of precincts
    model.x = pyo.Var(precincts, domain=pyo.Binary)
    model.z = pyo.Var(list(neighborhood_dict.keys()), domain=pyo.Binary)
    print(f"Variables Generated")

    #objective function (sums over the residences and precincts and seeks to minimize the average distance traveled by
    #residences with an added penalty for residences that are beyond the mean
    print(f"Defining Objective function.")
    if beta==0:
        def obj_rule(model):
            return (1/total_pop)*sum(pop_dict[c]*neighborhood_dict[c,s]*model.z[c,s] for c,s in neighborhood_dict)
        model.obj = pyo.Objective(rule=obj_rule, sense=pyo.minimize)
        
    else:
        def obj_rule(model):
            return ((1/total_pop)*sum(pop_dict[c]*model.z[c,s]*(math.e**(-beta*alpha*neighborhood_dict[c,s])) for c,s in neighborhood_dict))
        model.obj = pyo.Objective(rule=obj_rule, sense=pyo.minimize)

    #sum of the number of the precincts to be opened must be equal to the previous number (p)
    print(f"Defining open precincts constraint.")
    def open_rule(model):
        return sum(model.x[s] for s in precincts) == precincts_open
    model.open_constraint = pyo.Constraint(rule=open_rule)
    
    #percent of new precincts not to exceed maxpctnew
    print(f"Defining max new precincts constraint.")
    def max_new(model):
        return sum(model.x[s] for s in new_locations) <= maxpctnew*precincts_open
    model.max_new_constraint = pyo.Constraint(rule=max_new)

    #assigns each census block to a single precinct in its neighborhood
    print(f"Defining residents assignment constraint.")
    def res_assigned_rule(model, c):
        return sum(model.z[c,s] for s in res_precinct_pairings[c]) == 1
    model.res_assigned_constraint = pyo.Constraint(res_precinct_pairings.keys(), rule=res_assigned_rule)

    #residences can only be covered by precincts that are opened
    print(f"Defining assigning residents to only open precincts constraint.")
    def precinct_open_rule(model,c,s):
        return (model.z[c,s]<= model.x[s])
    model.precinct_open_constraint = pyo.Constraint(neighborhood_dict.keys(), rule=precinct_open_rule)

    #respects capacity limits and prevents overcrowding by restricting the number that can go to a precinct to some scaling factor of the avg population per center
    print(f"Defining capacity constraint.")
    def capacity_rule(model,s):
        return (sum(pop_dict[c]*model.z[c,s] for c  in precinct_res_pairings[s])<=(capacity*total_pop/precincts_open))
    model.capcity_constraint = pyo.Constraint(precinct_res_pairings.keys(), rule=capacity_rule)
    print(f"Model complete.")
    return model

#function to compile the results into a dataframe
def get_results_df(model, pop_demographics, neighborhood_dict, pop_dict):
    
    distance_df = [{'id_orig':c, 'id_dest':s, 'distance_m':d} for (c,s),d in neighborhood_dict.items() if model.z[c,s].value==1.0]
    df1 = pd.DataFrame(distance_df).copy()
    
    #population_df = [{'id_orig':c, 'pop':p} for c,p in pop_dict.items()]
    #df2 = pd.DataFrame(population_df)
    df2 =   pop_demographics.copy()
    
    df = pd.merge(df1, df2, how='inner', on='id_orig')
    df = df.drop_duplicates()
    df = df.reset_index()
    return df

#function to determine the number of people assigned to each polling location
def get_precinct_pop_df(results_df):
    precincts_used = []
    for i in results_df.index:
        if results_df['id_dest'][i] not in precincts_used:
            precincts_used.append(results_df['id_dest'][i])
    precinct_pops = []
    for s in precincts_used:
        precinct_sum = []
        for i in results_df.index:
            if results_df['id_dest'][i] == s:
                precinct_sum.append(results_df['H7X001'][i])
                popsum = sum(precinct_sum)
        precinct_pops.append(popsum)
    precinct_pop_dict = dict(zip(precincts_used, precinct_pops))
    precinctpopdf = [{'id_dest':s, 'H7X001':p} for s,p in precinct_pop_dict.items()]
    df_precinct_pop = pd.DataFrame(precinctpopdf)
    
    return df_precinct_pop

#determine the average distance for the resulting block-location pairings
def get_average_distance(results_df):
    total_distance = sum(results_df['distance_m'][i]*results_df['H7X001'][i] for i in results_df.index)
    num_res = len(results_df['distance_m'])
    average_distance = total_distance/(sum(results_df['H7X001']))
    return average_distance

#calculate the EDE for the resulting block-location pairings
def get_y_EDE(beta, betazero, alpha, model, results_df):
    if abs(beta)>0:
        y_EDE = (-1/(beta*alpha))*math.log(model.obj())
    if beta==0:
        y_EDE = (-1/(betazero*alpha))*math.log((1/sum(results_df['H7X001']))*sum(results_df['H7X001'][c]*(math.e**(-betazero*alpha*results_df['distance_m'][c])) for c in results_df.index))
    return y_EDE

#loop through the different demographics and return the EDE for the respective demographics
def get_demographic_EDE(beta, betazero, alpha, model, results_df, demographic):
    if demographic == 'white':
        demographic='H7X002'
    if demographic == 'black':
        demographic = 'H7X003'
    if demographic == 'native':
        demographic = 'H7X004'
    if demographic == 'asian':
        demographic = 'H7X005'
    if demographic == 'hispanic':
        demographic ='H7Z010'
    if abs(beta)>0:
        demo_EDE = (-1/(beta*alpha))*math.log((1/sum(results_df[demographic]))*sum(results_df[demographic][c]*(math.e**(-beta*alpha*results_df['distance_m'][c])) for c in range(0,len(results_df[demographic]))))
    if beta==0:
        demo_EDE = (-1/(betazero*alpha))*math.log((1/sum(results_df[demographic]))*sum(results_df[demographic][c]*(math.e**(-betazero*alpha*results_df['distance_m'][c])) for c in range(0,len(results_df[demographic]))))
      
    return demo_EDE

#calculate the variance when optimizing for average distance
def get_avgvariance(average_distance, blackdemo, whitedemo, nativedemo, asiandemo, hispanicdemo):
    demolist = [blackdemo, whitedemo, nativedemo, asiandemo, hispanicdemo]
    variance = (1/len(demolist))*sum((average_distance-demo)**2 for demo in demolist)
    return variance

#caluculate the variance when optimizing for EDE
def get_EDEvariance(y_EDE, blackdemo, whitedemo, nativedemo, asiandemo, hispanicdemo):
    demolist = [blackdemo, whitedemo, nativedemo, asiandemo, hispanicdemo]
    variance = (1/len(demolist))*sum((y_EDE-demo)**2 for demo in demolist)
    return variance

#calculate the standard deviation when optimizing for EDE
def get_EDEdeviation(y_EDE, blackdemo, whitedemo, nativedemo, asiandemo, hispanicdemo):
    deviation = math.sqrt(get_EDEvariance(y_EDE, blackdemo, whitedemo, nativedemo, asiandemo, hispanicdemo))
    return deviation

#export the data to .txt and .csv files. Produce an output statement in the interface program
def export_data(CITY, YEAR, LEVEL, BETA, MAXPCTNEW, assignment_results_df, precinct_pop_df, average_distance, y_EDE, PRECINCTS_OPEN, NUMVARS, solve_time,blackdemo,whitedemo,nativedemo,asiandemo,hispanicdemo,avgvariance, EDEvariance, EDEdeviation, out_path):
    if BETA!=0:
        assignment_results_df.to_csv(f'{out_path}{CITY}_{YEAR}_{LEVEL}_{BETA}_{MAXPCTNEW}_Output.csv')
        precinct_pop_df.to_csv(f'{out_path}{CITY}_{YEAR}_{LEVEL}_{BETA}_{MAXPCTNEW}_PrecinctPopulationOutput.csv')
    if BETA==0:
        assignment_results_df.to_csv(f'{out_path}{CITY}_{YEAR}_{LEVEL}_BETA0_{MAXPCTNEW}_Output.csv')
        precinct_pop_df.to_csv(f'{out_path}{CITY}_{YEAR}_{LEVEL}_BETA0_{MAXPCTNEW}_PrecinctPopulationOutput.csv')
    df = assignment_results_df
    schools = df[df.id_dest.str.contains('|'.join(['school']))].copy()
    numschools = schools['id_dest'].nunique()
    if LEVEL =='original':
        if BETA!=0:
            summary = [f"Below are the summary statistics for {CITY} in the year {YEAR} only including prior locations as possible precinct location options.",
                       f"Average distance: {average_distance:.2f}",
                       f"BETA: {BETA:.1f}",
                       f"MAXPCTNEW: {MAXPCTNEW:.2f}",
                       f"y_EDE: {y_EDE:.2f}",
                       f"Number of opened precincts is: {PRECINCTS_OPEN}",
                       f"Black EDE:{blackdemo:.2f}",
                       f"White EDE:{whitedemo:.2f}",
                       f"Native EDE:{nativedemo:.2f}",
                       f"Asian EDE:{asiandemo:.2f}",
                       f"Hispanic EDE:{hispanicdemo:.2f}",
                       f"The variance from the average distance is: {avgvariance:.2f}",
                       f"The variance from the y_EDE distance is: {EDEvariance:.2f}",
                       f"The standard deviation from the EDE for the demographics is: {EDEdeviation:.2f}",
                       f"Number of variables created: {NUMVARS}.",
                       f"Time to solve is: {solve_time:.2f} seconds ({solve_time/3600:.2f} hours)."]
            with open(f'{out_path}{CITY}_{YEAR}_{LEVEL}_{BETA}_{MAXPCTNEW}_summary.txt','w') as f:
                for stat in summary:
                    f.write(stat)
                    f.write('\n')
        if BETA==0:
            summary = [f"Below are the summary statistics for {CITY} in the year {YEAR} only including prior locations as possible precinct location options when minimizing for average distance.",
                       f"Average distance: {average_distance:.2f}",
                       f"BETA: {BETA:.1f}",
                       f"MAXPCTNEW: {MAXPCTNEW:.2f}",
                       f"y_EDE: {y_EDE:.2f}",
                       f"Number of opened precincts is: {PRECINCTS_OPEN}",
                       f"Black EDE:{blackdemo:.2f}",
                       f"White EDE:{whitedemo:.2f}",
                       f"Native EDE:{nativedemo:.2f}",
                       f"Asian EDE:{asiandemo:.2f}",
                       f"Hispanic EDE:{hispanicdemo:.2f}",
                       f"The variance from the average distance is: {avgvariance:.2f}",
                       f"The variance from the y_EDE distance is: {EDEvariance:.2f}",
                       f"The standard deviation from the EDE for the demographics is: {EDEdeviation:.2f}",
                       f"Number of variables created: {NUMVARS}.",
                       f"Time to solve is: {solve_time:.2f} seconds ({solve_time/3600:.2f} hours)."]
            with open(f'{out_path}{CITY}_{YEAR}_{LEVEL}_BETA0_{MAXPCTNEW}_summary.txt','w') as f:
                for stat in summary:
                    f.write(stat)
                    f.write('\n')
    if LEVEL =='expanded':
        schools = df[df.id_dest.str.contains('|'.join(['school']))].copy()
        numschools = schools['id_dest'].nunique()
        print(f"The number of schools that will be opened is {numschools}")
        pre = df[df.id_dest.str.contains('|'.join(['poll_']))]
        numprecincts = pre['id_dest'].nunique()
        print(f"The number of previously used precincts that will be opened is {numprecincts}")
        if BETA!=0:
            summary = [f"Below are the summary statistics for {CITY} in the year {YEAR} including prior locations and schools as possible precinct location options.",
                       f"Average distance: {average_distance:.2f}",
                       f"BETA: {BETA:.1f}",
                       f"MAXPCTNEW: {MAXPCTNEW:.2f}",
                       f"y_EDE: {y_EDE:.2f}",
                       f"Black EDE:{blackdemo:.2f}",
                       f"White EDE:{whitedemo:.2f}",
                       f"Native EDE:{nativedemo:.2f}",
                       f"Asian EDE:{asiandemo:.2f}",
                       f"Hispanic EDE:{hispanicdemo:.2f}",
                       f"The variance from the average distance is: {avgvariance:.2f}",
                       f"The variance from the y_EDE distance is: {EDEvariance:.2f}",
                       f"The standard deviation from the EDE for the demographics is: {EDEdeviation:.2f}",
                       f"Number of opened precincts is: {numprecincts}",
                       f"Number of opened schools is: {numschools}",
                       f"Number of variables created: {NUMVARS}.",
                       f"Time to solve is: {solve_time:.2f} seconds ({solve_time/3600:.2f} hours)."]
            with open(f'{out_path}{CITY}_{YEAR}_{LEVEL}_{BETA}_{MAXPCTNEW}_summary.txt','w') as f:
                for stat in summary:
                    f.write(stat)
                    f.write('\n')
                
        if BETA==0:
            summary = [f"Below are the summary statistics for {CITY} in the year {YEAR} including prior locations and schools as possible precinct location options when minimizing for average distance.",
                       f"Average distance: {average_distance:.2f}",
                       f"BETA: {BETA:.1f}",
                       f"MAXPCTNEW: {MAXPCTNEW:.2f}",
                       f"y_EDE: {y_EDE:.2f}",
                       f"Black EDE:{blackdemo:.2f}",
                       f"White EDE:{whitedemo:.2f}",
                       f"Native EDE:{nativedemo:.2f}",
                       f"Asian EDE:{asiandemo:.2f}",
                       f"Hispanic EDE:{hispanicdemo:.2f}",
                       f"The variance from the average distance is: {avgvariance:.2f}",
                       f"The variance from the y_EDE distance is: {EDEvariance:.2f}",
                       f"The standard deviation from the EDE for the demographics is: {EDEdeviation:.2f}",
                       f"Number of opened precincts is: {numprecincts}", 
                       f"Number of opened schools is: {numschools}",
                       f"Number of variables created: {NUMVARS}.",
                       f"Time to solve is: {solve_time:.2f} seconds ({solve_time/3600:.2f} hours)."]
            with open(f'{out_path}{CITY}_{YEAR}_{LEVEL}_BETA0_{MAXPCTNEW}_summary.txt','w') as f:
                for stat in summary:
                    f.write(stat)
                    f.write('\n')
    if LEVEL =='full':
        schools = df[df.id_dest.str.contains('|'.join(['school']))].copy()
        numschools = schools['id_dest'].nunique()
        print(f"The number of schools that will be opened is {numschools}")
        pre = df[df.id_dest.str.contains('|'.join(['poll_']))]
        numprecincts = pre['id_dest'].nunique()
        print(f"The number of previously used precincts that will be opened is {numprecincts}")
        numcentroids = PRECINCTS_OPEN-numprecincts-numschools
        print(f"The number of block group centroids that will be used is {numcentroids}")
        if BETA!=0:
            summary = [f"Below are the summary statistics for {CITY} in the year {YEAR} including prior locations, schools, and census block group centroids as possible precinct location options.",
                       f"Average distance: {average_distance:.2f}",
                       f"BETA: {BETA:.1f}",
                       f"MAXPCTNEW: {MAXPCTNEW:.2f}",
                       f"y_EDE: {y_EDE:.2f}",
                       f"Black EDE:{blackdemo:.2f}",
                       f"White EDE:{whitedemo:.2f}",
                       f"Native EDE:{nativedemo:.2f}",
                       f"Asian EDE:{asiandemo:.2f}",
                       f"Hispanic EDE:{hispanicdemo:.2f}",
                       f"The variance from the average distance is: {avgvariance:.2f}",
                       f"The variance from the y_EDE distance is: {EDEvariance:.2f}",
                       f"The standard deviation from the EDE for the demographics is: {EDEdeviation:.2f}",
                       f"Number of opened precincts is: {numprecincts}", 
                       f"Number of opened schools is: {numschools}",
                       f"Number of centroids utilized is: {numcentroids}",
                       f"Number of variables created: {NUMVARS}.",
                       f"Time to solve is: {solve_time:.2f} seconds ({solve_time/3600:.2f} hours)."]
            with open(f'{out_path}{CITY}_{YEAR}_{LEVEL}_{BETA}_{MAXPCTNEW}_summary.txt','w') as f:
                for stat in summary:
                    f.write(stat)
                    f.write('\n')
        if BETA==0:
            summary = [f"Below are the summary statistics for {CITY} in the year {YEAR} including prior locations, schools, and census block group centroids as possible precinct location options when minimizing for average distance.",
                       f"Average distance: {average_distance:.2f}",
                       f"BETA: {BETA:.1f}",
                       f"MAXPCTNEW: {MAXPCTNEW:.2f}",
                       f"y_EDE: {y_EDE:.2f}",
                       f"Black EDE:{blackdemo:.2f}",
                       f"White EDE:{whitedemo:.2f}",
                       f"Native EDE:{nativedemo:.2f}",
                       f"Asian EDE:{asiandemo:.2f}",
                       f"Hispanic EDE:{hispanicdemo:.2f}",
                       f"The variance from the average distance is: {avgvariance:.2f}",
                       f"The variance from the y_EDE distance is: {EDEvariance:.2f}",
                       f"The standard deviation from the EDE for the demographics is: {EDEdeviation:.2f}",
                       f"Number of opened precincts is: {numprecincts}",
                       f"Number of opened schools is: {numschools}",
                       f"Number of centroids utilized is: {numcentroids}",
                       f"Number of variables created: {NUMVARS}.",
                       f"Time to solve is: {solve_time:.2f} seconds ({solve_time/3600:.2f} hours)."]
            with open(f'{out_path}{CITY}_{YEAR}_{LEVEL}_BETA0_{MAXPCTNEW}_summary.txt','w') as f:
                for stat in summary:
                    f.write(stat)
                    f.write('\n')
            
    print(f"Data exported. Check folder {out_path} for results.") 
    print(f"Average Distance = {average_distance:.2f};")
    print(f"y_EDE = {y_EDE:.2f};")
    print(f"Beta = {BETA};") 
    print(f"Number of Variables: {NUMVARS}") 
    
    return 

def optimize(city, year, level, beta, beta_zero =-2, maxpctnew=1, time_limit=28800, out_path="results\\"):
    '''
    city -- in ['Atlanta', 'Baltimore', 'Cincinnati', 'Salem']
    year -- in ['2016', '2012']
    level -- in ['original', 'expanded', 'full']
    beta -- in [-2,0] (further from 0 => more aversion to inequality) (default is -2)
    betazero -- in [-2,0) used to calculate EDE of solution when beta=0 
    maxpctnew -- in [0,1] percent of new locations allowed (default is 1)
    time_limit -- in (0,\infty) seconds (default is 28800 (8 hours))
    out_path -- path to results directory (defaulty is 'results\\')
    '''
    
    CITY=city
    YEAR=year
    LEVEL=level
    BETA=beta
    MAXPCTNEW=maxpctnew
    if beta==0:
        BETAZERO = beta_zero
    else:
        BETAZERO = beta

    print('\n')
    print('*'*70)
    print(f'Running: {CITY}, {YEAR}, {level}, beta={beta}, betazero={BETAZERO}, maxpctnew={MAXPCTNEW}')
    print('*'*70)
    
    #data .csv file
    city_to_file = {'Atlanta': 'atlanta.csv',
                    'Cincinnati': 'cincinnati.csv',
                    'Richmond': 'richmond.csv',
                    'Salem': 'salem.csv',
                    'Dallas': 'dallas.csv'}
    


    #SETS
    dist = city_to_file[CITY]

    basedist = gd.get_basedist(dist, CITY, YEAR)
    print(f'Base Distances: {basedist.shape}')
    #print(basedist.head())
    dataframe = gd.get_dist_df(dist, CITY, LEVEL, YEAR)
    print(f'Full Distances: {dataframe.shape}')
    #print(dataframe.head())

    #reading in the various dataframes
    #print out progress
    POP_DICT = gd.get_id_pop_dict(dataframe)
    POP_DEMOGRAPHICS = gd.get_pop_demographics(dataframe)
    print(f"Demographics read in")
    RESIDENCES = gd.get_residential_ids(dataframe)
    print(f"Set of {len(RESIDENCES)} residence ids read in")
    PRECINCTS = gd.get_precinct_ids(dataframe)
    print(f"Set of {len(PRECINCTS)} original and new potential locations read in")
    NEW_LOCATIONS = gd.get_new_location_ids(dataframe)
    print(f"Set of {len(NEW_LOCATIONS)} potential new locatins read in")
    MAX_MIN_DIST = 1.2*gd.get_max_min_dist(basedist)
    print(f"MaxMinDistance read in")
    DISTANCE_DF = gd.dist_df(dataframe)
    print(f"Distance df read in")
    VALID_DISTS = gd.valid_dists(dataframe)
    print(f"Valid distance df read in")
    NEIGHBORHOOD_DICT = gd.neighborhood_distances(MAX_MIN_DIST, dataframe)
    print(f"Neighborhood df read in")
    RES_PRECINCT_PAIRINGS = gd.res_precinct_pairings(MAX_MIN_DIST, dataframe)
    print(f"Resident precinct pairs df read in")
    PRECINCT_RES_PAIRINGS = gd.precinct_res_pairings(MAX_MIN_DIST, dataframe)
    print(f"Precinct resident pairs df read in")
    
    #PARAMETERS
    PRECINCTS_OPEN = len(gd.get_precinct_ids(basedist))
    print(f"The number of precincts that will be open is {PRECINCTS_OPEN}")

    #scaling factor for capacity
    CAPACITY = 1.5

    #read in alpha
    ALPHA = gd.alpha_def(MAX_MIN_DIST, basedist)

    #set time limit for run time
    time_limit = 28800 # 8 hours
    #time_limit = 1800 # 30 minutes

    #placeholder for demographic value
    DEMOGRAPHIC = 5
    
    #used to track how long it has taken
    timestart = time.time()

    #read in the model
    ea_model = equal_access(residences=RESIDENCES, 
                  precincts=PRECINCTS,
                  pop_dict=POP_DICT,
                  pop_demographics=POP_DEMOGRAPHICS,
                  neighborhood_dict=NEIGHBORHOOD_DICT,
                  res_precinct_pairings=RES_PRECINCT_PAIRINGS,
                  precinct_res_pairings=PRECINCT_RES_PAIRINGS,
                  city=CITY,    
                  beta=BETA,
                  betazero = BETAZERO,
                  alpha=ALPHA,
                  capacity=CAPACITY,
                  precincts_open=PRECINCTS_OPEN,
                  demographic=DEMOGRAPHIC,
                  new_locations=NEW_LOCATIONS,
                  maxpctnew=MAXPCTNEW)

    print(f"The model has been read in at time {time.time()}.")

    #can change the solver
    solver_name = 'gurobi'
    #solver_name = 'glpk'

    solver = pyo.SolverFactory(solver_name)

    if solver_name == 'cplex':
        solver.options['timelimit'] = time_limit
    elif solver_name == 'glpk':        
        solver.options['tmlim'] = time_limit
    elif solver_name == 'gurobi':          
        solver.options['TimeLimit'] = time_limit

    start_time = time.time()
    read_time = start_time-timestart
    print(f"\nTime for model to be read in is {read_time:.2f} seconds\n")
    results = solver.solve(ea_model, tee=True)
    solve_time = time.time() - start_time

    #print updates on status
    if ((results.solver.status == SolverStatus.ok) and
        (results.solver.termination_condition == TerminationCondition.optimal)):
        # Do something when the solution in optimal and feasible
        exit_status = 'Optimal'
        lower = results['Problem'][0]['Lower bound']
        upper = results['Problem'][0]['Upper bound']
        gap = abs(lower-upper)/abs(upper)
    elif ((results.solver.status == SolverStatus.aborted) and
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
        
    #compile the results into dataframes
    assignment_results_df = get_results_df(ea_model, POP_DEMOGRAPHICS, NEIGHBORHOOD_DICT, POP_DICT)
    precinct_pop_df = get_precinct_pop_df(assignment_results_df)

    #calculate average distance and EDE using the results
    average_distance = get_average_distance(assignment_results_df)
    y_EDE = get_y_EDE(BETA, BETAZERO, ALPHA, ea_model, assignment_results_df)

    #calculate the number of decision variables used in the model
    NUMVARS = (len(list(ea_model.z))+len(list(ea_model.x)))
    
    #loop through the different demographics of interest and get statistics
    DEMOGRAPHIC = 'black'
    blackdemo = demographic_EDE = get_demographic_EDE(BETA, BETAZERO, ALPHA, ea_model, assignment_results_df, DEMOGRAPHIC)
    DEMOGRAPHIC = 'white'
    whitedemo = demographic_EDE = get_demographic_EDE(BETA, BETAZERO, ALPHA, ea_model, assignment_results_df, DEMOGRAPHIC)
    DEMOGRAPHIC = 'native'
    nativedemo = demographic_EDE = get_demographic_EDE(BETA, BETAZERO, ALPHA, ea_model, assignment_results_df, DEMOGRAPHIC)
    DEMOGRAPHIC = 'asian'
    asiandemo = demographic_EDE = get_demographic_EDE(BETA, BETAZERO, ALPHA, ea_model, assignment_results_df, DEMOGRAPHIC)
    DEMOGRAPHIC = 'hispanic'
    hispanicdemo = demographic_EDE = get_demographic_EDE(BETA, BETAZERO, ALPHA, ea_model, assignment_results_df, DEMOGRAPHIC)

    #find variance and deviation statistics
    avgvariance = get_avgvariance(average_distance, blackdemo, whitedemo, nativedemo, asiandemo, hispanicdemo)
    EDEvariance = get_EDEvariance(y_EDE, blackdemo, whitedemo, nativedemo, asiandemo, hispanicdemo)
    EDEdeviation = get_EDEdeviation(y_EDE, blackdemo, whitedemo, nativedemo, asiandemo, hispanicdemo)
    
    #export data to .csv and .txt files
    export_data(CITY, YEAR, LEVEL, BETA, MAXPCTNEW,
                assignment_results_df, precinct_pop_df, 
                average_distance, y_EDE, PRECINCTS_OPEN, 
                NUMVARS, solve_time, blackdemo,whitedemo,
                nativedemo,asiandemo,hispanicdemo, avgvariance, 
                EDEvariance, EDEdeviation, out_path)
    
    return
