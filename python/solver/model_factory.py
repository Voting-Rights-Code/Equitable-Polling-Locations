#######################################
#Created on 6 December 2023
#
#@author: Voting Rights Code
#@attribution: based off of code by Josh Murell
#######################################

'''
Factory function to build the pyomo population model
'''

import math
import warnings

import pyomo.environ as pyo

from python.utils import timer

from .constants import (
  LOC_ID_ORIG, LOC_ID_DEST, LOC_TOTAL_POPULATION, LOC_DISTANCE_M,
  LOC_WEIGHTED_DIST, POLLING, LOC_LOCATION_TYPE, LOC_DEST_TYPE, MEAN,
  KP_FACTOR, MAX, RESULT_NEW_LOCATION, UNIQUE,
)


from .model_config import PollingModelConfig
from .model_data import (
    get_max_min_dist,
)

# SCIP can only handle values up to 1e20
MAX_KP_FACTOR = 9e19

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
    kp_factor = pyo.Param
    '''KP factor for each reisdence, precinct pair'''
    new_locations = pyo.Param
    '''Boolean indicating whether a precint is a new location'''

    open: pyo.Var
    '''Boolean variable indicating whether the precinct is open'''
    matching: pyo.Var
    '''Boolean variable indicating whether the precinct and residence pair is matched'''


def build_objective_rule(
    config: PollingModelConfig,
    #residence_precinct_pairs: list,
    #dist_df: pd.DataFrame,
    total_pop: int,
    alpha: float,
    *,
    site_penalty: float=0,
    kp_penalty_parameter: float=0,
):
    '''The function to be minimized:
    Variables: model.matching, indexed by reisidence precinct pairs'''
    if site_penalty:
        def obj_rule_0(model: pyo.ConcreteModel):
            average_weighted_distances = (
                sum(
                    model.matching[pair] * model.weighted_dist[pair]
                    for pair in model.pairs
                ) / total_pop + sum(
                    model.open[site] * site_penalty
                    for site in model.penalized_sites
                )
            )

            return average_weighted_distances

        def obj_rule_not_0(model: pyo.ConcreteModel):
            average_weighted_distances = (
                (
                    sum(
                        model.population[pair[0]] * model.matching[pair] * model.kp_factor[pair]
                        for pair in model.pairs
                    ) / total_pop
                ) + (
                    math.exp(-config.beta * alpha * kp_penalty_parameter) * (model.penalty_exp - 1)
                )
            )
            return average_weighted_distances
    else:
        def obj_rule_0(model: pyo.ConcreteModel):
            #take average populated weighted distance
            average_weighted_distances = sum(
                model.matching[pair] * model.weighted_dist[pair]
                for pair in model.pairs
            ) / total_pop

            return average_weighted_distances

        def obj_rule_not_0(model: pyo.ConcreteModel):
            #take average by kp factor weight
            #pair[0] = residence
            average_weighted_distances = sum(
                model.population[pair[0]] * model.matching[pair] * model.kp_factor[pair]
                for pair in model.pairs
            ) / total_pop

            return average_weighted_distances

    return obj_rule_not_0 if config.beta else obj_rule_0


#@timer
def build_open_rule(
    precincts_open:int,
):
    '''Can have exactly precincts_open number of open precincts'''
    def open_rule(
            model: pyo.ConcreteModel,
        ) -> bool:
        return sum(
            model.open[precinct]
            for precinct in model.precincts
        ) == precincts_open

    return open_rule


#@timer
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

        return sum(
            model.open[precinct] * model.new_locations[precinct]
            for precinct in model.precincts
        ) <= maxpctnew*precincts_open

    return max_new_rule


def build_min_old_rule(
    config: PollingModelConfig,
    old_polls:int,
):
    '''a minimum percent of old polling locations must be included,
    skip if set to 0'''

    def min_old_rule(
            model: pyo.ConcreteModel,
        ) -> bool:
        if config.minpctold == 0:
            return pyo.Constraint.Skip
        else:
            return sum(
                model.open[precinct] * (1 - model.new_locations[precinct])
                for precinct in model.precincts
            ) >= config.minpctold*old_polls

    return min_old_rule


#@timer
def build_res_assigned_rule():
    '''assigns each census block to a single precinct in its neighborhood'''
    def res_assigned_rule(
            model: pyo.ConcreteModel,
            residence
        ) -> bool:
        return (
            sum(model.matching[residence, precinct]
            for precinct in model.within_residence_radius[residence]
        ) == 1)

    return res_assigned_rule


#@timer
def build_precinct_open_rule():
    '''residences can only be assigned to precincts that are opened'''
    def precinct_open_rule(
        model: pyo.ConcreteModel,
        res, prec,
    ) -> bool:
        return(model.matching[res,prec] <= model.open[prec])

    return precinct_open_rule


def build_exclude_sites_rule():
    '''exclude these sites from being selected'''
    def exclude_sites_rule(
        model: pyo.ConcreteModel,
        precinct
    ) -> bool:
        return model.open[precinct] == 0

    return exclude_sites_rule


def build_penalty_rule(alpha: float, beta: float, site_penalty: float):
    '''set the penalty factor'''
    def penalty_rule(model: pyo.ConcreteModel) -> bool:
        return (
            model.penalty == -alpha * beta * sum(
                model.open[s]*site_penalty
                for s in model.penalized_sites
            )
        )

    return penalty_rule


def build_penalty_approximation_rule():
    '''set the penalty factor'''
    def penalty_approximation_rule(model: pyo.ConcreteModel, linearization_point: float) -> bool:
        min_penalty_exp = math.exp(linearization_point) * (1 + model.penalty - linearization_point)

        return model.penalty_exp >= min_penalty_exp

    return penalty_approximation_rule


#@timer
def build_capacity_rule(
    config: PollingModelConfig,
    total_pop: int,
    precincts_open: int,
):
    '''
    Respects capacity limits and prevents overcrowding by restricting the number that can go to a precinct
    to some scaling factor of the avg population per center
    '''
    #modify the capacity according to the user defined default precints_open
    if config.fixed_capacity_site_number is None:
        #capacity rule uses capacity * total_pop / precincts open
        capacity = config.capacity
    else: #calculate capacity_rule by replacing precints_open with fixed_capacity_site_number
        capacity = config.capacity * precincts_open / config.fixed_capacity_site_number

    def capacity_rule(
        model: pyo.AbstractModel,
        precinct,
    ) -> bool:
        return sum(
            model.population[res]*model.matching[res,precinct]
            for res in model.within_precinct_radius[precinct]
        ) <= (capacity * total_pop / precincts_open)

    return capacity_rule


def compute_kp_factor(config: PollingModelConfig, alpha: float, dist_df):
    return math.e**(-config.beta * alpha * dist_df[LOC_DISTANCE_M])


@timer
def polling_model_factory(
    dist_df,
    alpha,
    config: PollingModelConfig, *,
    exclude_penalized_sites: bool=False,
    site_penalty: float=0,
    kp_penalty_parameter: float=0
) -> PollingModel:
    '''
        Returns the polling location pyomo model.
    '''

    if site_penalty and not kp_penalty_parameter:
        raise ValueError(f'kp_penalty_parameter must be positive if site_penalty is positive ({site_penalty=}')

    #define max_min parameter needed for certain calculations
    global_max_min_dist = get_max_min_dist(dist_df)
    max_min = config.max_min_mult * global_max_min_dist

    #Calculate number of old polling locations
    old_polls = len(set(dist_df[dist_df[LOC_DEST_TYPE] == POLLING][LOC_ID_DEST]))

    #Calculate precincts open value from data if not provided by user
    if config.precincts_open is None:
        precincts_open = old_polls
    else:
        precincts_open = config.precincts_open
    #The number of precincts to open might need to be reduced when
    #excluding penalized sites (penalty Model 2) to avoid infeasible model
    if exclude_penalized_sites:
        num_dests = len(set(dist_df[LOC_ID_DEST]) - set(config.penalized_sites))
        precincts_open = min(precincts_open, num_dests)

    ####define constants####
    #total population
    total_pop = dist_df.groupby(LOC_ID_ORIG)[LOC_TOTAL_POPULATION].agg(UNIQUE).str[0].sum()
    ####set model to be concrete####
    model = pyo.ConcreteModel()

    ####define model simple indices####
    #all possible precinct locations (unique)
    model.precincts = pyo.Set(initialize = list(set(dist_df[LOC_ID_DEST])))
    #all possible residence locations with population > 0 (unique)
    model.residences = pyo.Set(initialize = list(set(dist_df[LOC_ID_ORIG])))
    #residence, precint pairs
    model.pairs = model.residences * model.precincts
    #penalized sites
    if config.penalized_sites:
        penalized_sites = list(set(
            dist_df.loc[
                dist_df[LOC_LOCATION_TYPE].isin(config.penalized_sites),
                LOC_ID_DEST,
            ].unique())
        )
    else:
        penalized_sites = []
    model.penalized_sites = pyo.Set(initialize=penalized_sites)

    ####define model parameters####
    #Populations of residences
    model.population = pyo.Param(
        model.residences,
        initialize=dist_df.groupby(LOC_ID_ORIG)[LOC_TOTAL_POPULATION].agg(MEAN),
    )
    #Precinct residence distances

    model.distance = pyo.Param(
        model.pairs, initialize=dist_df[
            [LOC_ID_ORIG, LOC_ID_DEST, LOC_DISTANCE_M]
        ].set_index([LOC_ID_ORIG, LOC_ID_DEST]),
    )
    #population weighted distances
    model.weighted_dist = pyo.Param(
        model.pairs, initialize=dist_df[
            [LOC_ID_ORIG, LOC_ID_DEST, LOC_WEIGHTED_DIST]
        ].set_index([LOC_ID_ORIG, LOC_ID_DEST]),
    )

    #KP factor
    dist_df[KP_FACTOR] = compute_kp_factor(config, alpha, dist_df)
    # math.e**(-config.beta*alpha*dist_df[DISTANCE_M])
    max_kp_factor = dist_df.groupby(LOC_ID_ORIG)[KP_FACTOR].agg(MAX).max()
    if max_kp_factor > MAX_KP_FACTOR:
        # pylint: disable-next=line-too-long
        warnings.warn(f'Max kp_factor is {max_kp_factor}. SCIP can only handle values up to {MAX_KP_FACTOR+1}. Consider a less negative value of beta.')

    model.kp_factor = pyo.Param(
        model.pairs,
        initialize = dist_df[
            [LOC_ID_ORIG, LOC_ID_DEST, KP_FACTOR]
        ].set_index([LOC_ID_ORIG, LOC_ID_DEST]),
    )

    #new location marker
    dist_df[RESULT_NEW_LOCATION] = 0
    dist_df[RESULT_NEW_LOCATION].mask(
        dist_df[LOC_DEST_TYPE] != POLLING,
        1,
        inplace=True,
    )

    model.new_locations = pyo.Param(
        model.precincts,
        initialize=dist_df[
            [LOC_ID_DEST, RESULT_NEW_LOCATION]
        ].drop_duplicates().set_index([LOC_ID_DEST]),
    )

    ####define model variables####
    model.matching = pyo.Var(model.pairs, domain=pyo.Binary)
    model.open = pyo.Var(model.precincts, domain=pyo.Binary)

    if site_penalty:
        model.penalty_exp = pyo.Var(domain=pyo.NonNegativeReals)
        model.penalty = pyo.Var(domain=pyo.NonNegativeReals)

    ####define parameter dependent indices####
    #residences in precint radius
    model.within_residence_radius = pyo.Set(
        model.residences,
        initialize={
            res: [
                prec for prec in model.precincts
                if model.distance[(res, prec)] <= max_min
            ] for res in model.residences
        },
    )

    #precinct in residence radius
    model.within_precinct_radius = pyo.Set(
        model.precincts,
        initialize={
            prec: [
                res for res in model.residences
                if model.distance[(res, prec)] <= max_min
            ] for prec in model.precincts
        },
    )

    # Set the objective function
    obj_rule = build_objective_rule(
        config, total_pop, alpha, site_penalty=site_penalty,
        kp_penalty_parameter=kp_penalty_parameter,
    )
    model.obj = pyo.Objective(rule=obj_rule, sense=pyo.minimize)

    #### Define Constraints
    open_rule = build_open_rule(precincts_open)
    model.open_constraint = pyo.Constraint(rule=open_rule)

    if site_penalty:
        penalty_rule = build_penalty_rule(alpha, config.beta, site_penalty)
        model.penalty_constraint = pyo.Constraint(rule=penalty_rule)

        num_penalized_sites = len(model.penalized_sites)
        linearization_points = [
            -alpha * config.beta * i * site_penalty
            for i in range(num_penalized_sites + 1)
        ]
        penalty_approximation_rule = build_penalty_approximation_rule()
        model.penalty_approximation_constraint = pyo.Constraint(
            linearization_points, rule=penalty_approximation_rule,
        )

    #percent of new precincts not to exceed maxpctnew
    max_new_rule = build_max_new_rule(config, precincts_open)
    model.max_new_constraint = pyo.Constraint(rule=max_new_rule)

    #optionally exclude penalized sites
    if exclude_penalized_sites:
        exclude_sites_rule = build_exclude_sites_rule()
        model.exclude_sites_constraint = pyo.Constraint(
            model.penalized_sites, rule=exclude_sites_rule,
        )

    #percent of established precincts not to dip below minpctold
    min_old_rule = build_min_old_rule(config, old_polls)
    model.min_old_constraint = pyo.Constraint(rule=min_old_rule)

    #assigns each census block to a single precinct in its neighborhood
    res_assigned_rule = build_res_assigned_rule()
    model.res_assigned_constraint = pyo.Constraint(
        model.residences, rule=res_assigned_rule,
    )

    #residences can only be covered by precincts that are opened
    precinct_open_rule = build_precinct_open_rule()
    model.precinct_open_constraint = pyo.Constraint(
        model.pairs, rule=precinct_open_rule,
    )

    #Each polling location can serve a max population
    # that is a multiplicative factor of total_population/ precincts_open
    capacity_rule = build_capacity_rule(
        config=config,
        total_pop=total_pop,
        precincts_open=precincts_open,
    )

    model.capacity_constraint = pyo.Constraint(
        model.precincts, rule=capacity_rule,
    )

    #model.obj.pprint()
    return model

