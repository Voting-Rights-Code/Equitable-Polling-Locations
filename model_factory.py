'''
Factory function to build the pyomo population model
'''

from dataclasses import dataclass
import math

import pandas as pd
import pyomo.environ as pyo


from data_for_model import (
    get_max_min_dist,
)

from utils import timer

class PollingModel(pyo.ConcreteModel):
    ''' An extention of the pyomo ConcreteModel to document variables '''

    precincts: pyo.Set
    '''all possible precinct locations (unique)'''
    residences = pyo.Set
    '''all possible residence locations with population > 0 (unique)'''
    pairs = pyo.Set
    '''all (precinct, residence) pairs'''
    within_residence_radius = pyo.Set
    '''list of precincts within radius of each residence'''
    within_precincts_radius = pyo.Set
    '''list of residences within radius of each precinct'''

    population = pyo.Param
    '''Populations of residences'''
    distance = pyo.Param
    '''Precinct residence distances'''
    weighted_dist = pyo.Param
    '''population weighted distances'''
    KP_factor = pyo.Param
    '''KP factor for each reisdence, precinct pair'''
    new_locations = pyo.Param
    '''Boolean indicating whether a precint is a new location'''

    open: pyo.Var
    '''Boolean variable indicating whether the precinct is open'''
    matching: pyo.Var
    '''Boolean variable indicating whether the precinct and residence pair is matched'''


@dataclass
class PollingModelConfig:
    location: str
    '''Name of the county or city of interest'''
    year: list
    '''list of years to be studied'''
    level: str
    '''{'original': consider only the original polling locations,
        'expanded': consider all schools
        'full': consider all schools and census block group centroids}'''
    beta: float
    '''level of inequality aversion: [-10,0], where 0 indicates indifference, and thus uses the mean. -2 is a good number '''
    time_limit_seconds: int
    '''How long the solver should try to find a solution'''
    precincts_open: int = None
    '''The total number of precincts to be used this year. If no
    user input is given, this is calculated to be the number of
    polling places identified in the data.'''
    maxpctnew: float = 1.0
    '''The percent on new polling places (not already defined as a
    polling location) permitted in the data. Default = 1. I.e. can replace all existing locations'''
    minpctold: float = 0
    '''The minimun number of polling places (those already defined as a
    polling location) permitted in the data. Default = 0. I.e. can replace all existing locations'''
    max_min_mult: float = 1.0
    '''A multiplicative factor for the min_max distance caluclated
    from the data. Should be >= 1. Default = 1.'''
    capacity: float = 1.0
    '''A multiplicative factor for calculating the capacity constraint. Should be >= 1. Default = 1.'''
@timer
def build_objective_rule(
        config: PollingModelConfig,
        #residence_precinct_pairs: list,
        #dist_df: pd.DataFrame,
        total_pop: int,
    ):
    '''The function to be minimized:
    Variables: model.matching, indexed by reisidence precinct pairs'''
    def obj_rule_0(model):
        #take average populated weighted distance
        average_weighted_distances = sum(model.matching[pair]* model.weighted_dist[pair] for pair in model.pairs)/total_pop
        return (average_weighted_distances)
    def obj_rule_not_0(model):
        #take average by kp factor weight
        #pair[0] = residence
        average_weighted_distances = sum(model.population[pair[0]]* model.matching[pair]* model.KP_factor[pair] for pair in model.pairs)/total_pop
        return (average_weighted_distances)
    if config.beta == 0:
        return obj_rule_0
    if config.beta != 0: 
        return obj_rule_not_0

@timer
def build_open_rule(
    precincts_open:int,
    ):
    '''Can have exactly precincts_open number of open precincts'''
    def open_rule(
            model: pyo.ConcreteModel,
        ) -> bool:
        return sum(model.open[precinct] for precinct in model.precincts) == precincts_open
    return open_rule

@timer
def build_max_new_rule(
    config: PollingModelConfig,
    precincts_open:int,
):
    '''percent of new open precincts cannot exceed maxpctnew,
    skip if no new locations in data'''
    maxpctnew = config.maxpctnew

    def max_new_rule(
            model: pyo.ConcreteModel,
        ) -> bool:
        if not any(model.new_locations[precincts] for precincts in model.precincts):
            return pyo.Constraint.Skip
        else:
            return sum(model.open[precinct]* model.new_locations[precinct] for precinct in model.precincts) <= maxpctnew*precincts_open
    return max_new_rule

def build_min_old_rule(
    config: PollingModelConfig,
    precincts_open:int,
):
    '''percent of new open precincts cannot exceed maxpctnew,
    skip if no new locations in data'''
    minpctold = config.minpctold

    def min_old_rule(
            model: pyo.ConcreteModel,
        ) -> bool:
        if all(model.new_locations[precincts] for precincts in model.precincts):
            return pyo.Constraint.Skip
        else:
            return sum(model.open[precinct]* (1-model.new_locations[precinct]) for precinct in model.precincts) >= minpctold*precincts_open
    return min_old_rule

@timer
def build_res_assigned_rule(
):
    '''assigns each census block to a single precinct in its neighborhood'''
    def res_assigned_rule(
            model: pyo.ConcreteModel,
            residence
        ) -> bool:
        return (sum(model.matching[residence, precinct] for precinct in model.within_residence_radius[residence]) == 1)
    return res_assigned_rule

@timer
def build_precinct_open_rule():
    '''residences can only be assigned to precincts that are opened'''
    def precinct_open_rule(
        model: pyo.ConcreteModel,
        res, prec,
    ) -> bool:
        return(model.matching[res,prec]<= model.open[prec])
    return precinct_open_rule

@timer
def build_capacity_rule(
        config: PollingModelConfig,
        total_pop: int,
        precincts_open: int,
    ):
    '''
    Respects capacity limits and prevents overcrowding by restricting the number that can go to a precinct to some scaling factor of the avg population per center
    '''
    capacity = config.capacity

    def capacity_rule(
        model: pyo.AbstractModel,
        precinct,
    ) -> bool:
        return (sum(model.population[res]*model.matching[res,precinct] for res in model.within_precinct_radius[precinct])<=(capacity*total_pop/precincts_open))
    return capacity_rule

@timer
def polling_model_factory(dist_df, alpha, config: PollingModelConfig) -> PollingModel:
    '''
        Returns the polling locatoin pyomo model.
    '''
    #define max_min parameter needed for certain calculations
    global_max_min_dist = get_max_min_dist(dist_df)
    max_min = config.max_min_mult* global_max_min_dist
    
    #Calculate precincts open value from data if not provided by user
    if config.precincts_open == None:
        precincts_open = len(set(dist_df[dist_df['dest_type']=='polling']['id_dest']))
    else:
        precincts_open = config.precincts_open

    ####define constants####
    #total population
    total_pop = dist_df.groupby('id_orig')['population'].agg('unique').str[0].sum() 
    ####set model to be concrete####
    model = pyo.ConcreteModel()

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
    dist_df['KP_factor'] = math.e**(-config.beta*alpha*dist_df['distance_m'])
    model.KP_factor = pyo.Param(model.pairs, initialize = dist_df[['id_orig', 'id_dest', 'KP_factor']].set_index(['id_orig', 'id_dest']))
    #new location marker
    dist_df['new_location'] = 0
    dist_df['new_location'].mask(dist_df['dest_type']!='polling', 1, inplace = True)

    model.new_locations = pyo.Param(model.precincts, initialize = dist_df[['id_dest', 'new_location']].drop_duplicates().set_index(['id_dest']))

    ####define model variables####  
    model.matching = pyo.Var(model.pairs, domain=pyo.Binary )
    model.open = pyo.Var(model.precincts, domain=pyo.Binary )

    ####define parameter dependent indices####
    #residences in precint radius
    model.within_residence_radius = pyo.Set(model.residences, initialize = {res:[prec for prec in model.precincts if model.distance[(res,prec)] <= max_min] for res in model.residences})
    #precinct in residence radius
    model.within_precinct_radius = pyo.Set(model.precincts, initialize = {prec:[res for res in model.residences if model.distance[(res,prec)] <= max_min] for prec in model.precincts})

    # Set the objective function
    obj_rule = build_objective_rule(config,                 total_pop)
    model.obj = pyo.Objective(rule=obj_rule, sense=pyo.minimize)

    #### Define Constraints
    open_rule = build_open_rule(precincts_open)
    model.open_constraint = pyo.Constraint(rule=open_rule)

    #percent of new precincts not to exceed maxpctnew
    max_new_rule = build_max_new_rule(config, precincts_open)
    model.max_new_constraint = pyo.Constraint(rule=max_new_rule)

    #percent of established precincts not to dip below minpctold
    min_old_rule = build_min_old_rule(config, precincts_open)
    model.min_old_constraint = pyo.Constraint(rule=min_old_rule)

    #assigns each census block to a single precinct in its neighborhood
    res_assigned_rule = build_res_assigned_rule()
    model.res_assigned_constraint = pyo.Constraint(model.residences, rule=res_assigned_rule)

    #residences can only be covered by precincts that are opened
    precinct_open_rule = build_precinct_open_rule()
    model.precinct_open_constraint = pyo.Constraint(model.pairs, rule=precinct_open_rule)

    capacity_rule = build_capacity_rule(
        config=config,
        total_pop=total_pop,
        precincts_open=precincts_open,
    )
 
    model.capacity_constraint = pyo.Constraint(model.precincts, rule=capacity_rule)

    #model.obj.pprint()
    return model
