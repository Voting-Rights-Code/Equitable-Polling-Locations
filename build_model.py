from test_config_refactor import * #For testing only. Remove later 
import data_for_model as data
import pyomo.environ as pyo
import pandas as pd


#####################################
#Get key data frames and constants
#####################################

####dataframes####
#TODO: Check if really both of these are needed
basedist = get_base_dist(location, year)
dist_df = get_dist_df(basedist, level, year)

####constants####
alpha = alpha_def(basedist, beta)
global_max_min_dist = get_max_min_dist(basedist)

#check if poll number has been assigned in config
#if not, give it the default number of polls in the file
poll_number_exists = 'precincts_open' in  globals() or 'precincts_open' in  locals()
if not poll_number_exists:
    #Set it to the number of polling locations in the data
    precincts_open = len(set(dist_df[dist_df['dest_type']=='polling']['id_dest']))


def build_model(dist_df = dist_df, beta = beta, alpha = alpha, max_min = global_max_min_dist, maxpctnew = maxpctnew, precincts_open = precincts_open):
    ####set model to be concrete####
    model = pyo.ConcreteModel()

    ####define model variables####
    #list of all possible precinct locations (unique)
    precincts = list(set(dist_df['id_dest']))
    #list of all possible residence locations with population > 0 (unique)
    residences = list(set(dist_df['id_orig']))
    #list of unique residence, precint pairs
    residence_precinct_pairs = list(itertools.product(residences, precincts)) #TODO: This is needed because dist_df has dups in these pairs?
    model.x = pyo.Var(precincts, domain=pyo.Binary)
    model.z = pyo.Var(residence_precinct_pairs, domain=pyo.Binary)

    ####helper columns for objective function#####
    #Weighted_dist(ance) = population of id_orig * distance from id_orig to id_dest
    #K(olm)P(ollak)_factor = population of id_orig * math.e**(-beta*alpha*distance from id_orig to id_dest)
    dist_df['Weighted_dist'] = dist_df['H7X001'] * dist_df['distance_m']
    dist_df['KP_factor'] = dist_df['H7X001'] * (math.e**(-beta*alpha*dist_df['distance_m']))
    total_pop = dist_df.groupby('id_orig')['H7X001'].aggregate('mean')

    ####define objective function####
    def obj_rule(model):
        if beta == 0:
            weighting_column = 'Weighted_dist'
        else: #(beta != 0)
            weighting_column = 'KP_factor'
        weighted_distances = list(
                            list(dist_df[(dist_df['id_origin'] == resident_id) & (dist_df['id_dest'] == precinct_id)][weighting_column])[0] *
                            model.z[resident_id,precinct_id] 
                            for resident_id,precinct_id in residence_precinct_pairs
                            ) 
        #TODO: 1) can the model.z be brought into the data frame? that would be cleaner
        #TODO: 2) note that the first nested list is there so that this can function with duplicates. Fix after cleaning
        average_weighted_distances = (1/total_pop)*sum(weighted_distances)
        return (average_weighted_distances)
    
    model.obj = pyo.Objective(rule=obj_rule, sense=pyo.minimize)
    
    ####define objective constraints####
    #Open precincts constraint.
    def open_rule(model): 
        return sum(model.x[precint_id] for precint_id in precincts) == precincts_open
    model.open_constraint = pyo.Constraint(rule=open_rule)

    #percent of new precincts not to exceed maxpctnew
    new_locations = list(set(dist_df[(dist_df['dest_type']!='polling')]['id_dest']))
    def max_new(model):
        return sum(model.x[precint_id] for precint_id in new_locations) <= maxpctnew*precincts_open
    model.max_new_constraint = pyo.Constraint(rule=max_new)

    #assigns each census block to a single precinct in its neighborhood
    presincts_in_radius_of_residence = data.res_precinct_pairings(max_min, dist_df)
    def res_assigned_rule(model, residence_id):
        return sum(model.z[residence_id,precinct_id] for precinct_id in presincts_in_radius_of_residence[residence_id]) == 1
    model.res_assigned_constraint = pyo.Constraint(residences, rule=res_assigned_rule)

    #residences can only be covered by precincts that are opened
    print(f"Defining assigning residents to only open precincts constraint.")
    def precinct_open_rule(model,residence_id,precint_id):
        return (model.z[residence_id,precint_id]<= model.x[precint_id])
    model.precinct_open_constraint = pyo.Constraint(residence_precinct_pairs, rule=precinct_open_rule)

    #respects capacity limits and prevents overcrowding by restricting the number that can go to a precinct to some scaling factor of the avg population per center
    residences_in_radius_of_precinct = data.precinct_res_pairings(global_max_min_dist, dist_df)
    def capacity_rule(model,precinct_id):
        #TODO: nested list to account for duplicates. Remove when duplication fixed.
        return (sum(list(dist_df[residence_id]['H7X001'])[0]*model.z[residence_id,precinct_id] for residence_id  in residences_in_radius_of_precinct[precinct_id])<=(capacity*total_pop/precincts_open))
    model.capcity_constraint = pyo.Constraint(residence_precinct_pairs, rule=capacity_rule)
    return model



