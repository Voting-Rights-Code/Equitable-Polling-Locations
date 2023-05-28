#######################################
#Created on 27 May 2023
#
#@author: Voting Rights Code
#@attribution: Josh Murell 
#######################################

'''
Right now, this assumes that there exists a set of tables, one for each location, year
of the following columns:
[ , id_orig, id_dest, distance_m, city,	dest_type, H7X001, H7X002, H7X003, 
    H7X004, H7X005, H7Z010, JOIE001, poverty_0_50, poverty_50_99]

The functions in this file pull out the requisite data from this table for processing by the equal access model
'''
#TODO: (SA/CR) Need to write an automated script to read in the demographics part of this table for a given county 
#        from the ACS
#       TODO: (SA) Once the ingest is running, need to get the demographic column names into something sensible
#TODO: (all) Need to figure out how the distance is calculated and get that implemented at the county level from Google
#       TODO: (all) there is a lot of preprocessing of the data that is currently in the git repo. Need to know what that is
#               and preferably, see the code that creates that so that we may implement.
#TODO: (CR) Need to figure out where the data is going to be stored in the end.


#import modules
import pandas as pd
import math
import subprocess
import os
import itertools
from test_config_refactor import * #TODO: (SA) for testing only. remove later
 

##########################
#Data source
#currently assumes that the relevant .csvs are all in the git repo
##########################
#TODO: fix this when we know where the data is going to be eventually stored
git_dir = subprocess.Popen(['git', 'rev-parse', '--show-toplevel'], stdout=subprocess.PIPE).communicate()[0].rstrip().decode('utf-8')
data_dir = os.path.join(git_dir, 'datasets')

##########################
#Data_file_name dataframe
##########################
#TODO: This needs to be updated. Currenly only data is for Salem 2016, 2012
file_name_dict = {'Salem':'salem.csv'}
             

##########################
#read in data and get relevant dataframes for models
##########################
#returns dataframe of distances for the original case. This is to keep alpha constant amongst all cases
#TODO: originally, this function added a suffix of _year_num to locations tagged as poll. 
#       but this is currently in the column id_dest. Therefore not contained in this function
#TODO: How should I understand the id_dest poll_year_num. Does this involve multiplicity? I.e. if the same location is a polling
#       location in mulltiple years, does it show up twice, once as poll_year1_num1 and again as poll_year2_num2?

#This is a base data frame, used mostly for alpha calculation, but also other things.
#The output of this function, referred to as basedist, is the full dataset on file
#TODO: Susama and Chad need a walk through of what exactly these files contain. 
#       Specifically, are these all distances to all actual and potential polling locations?
def get_base_dist(location, year):
    if location not in file_name_dict.keys():
        raise ValueError(f'Do not currently have any data for {location}')
    file_name = file_name_dict[location]
    file_path = os.path.join(data_dir, file_name)
    df = pd.read_csv(file_path)
    #extract years
    polling_locations = set(df[df.id_dest.str.contains('poll')]['id_dest'])
    year_set = set(poll[5:9] for poll in polling_locations)
    if str(year) not in year_set:
        raise ValueError(f'Do not currently have any data for {location} for {year}')
    df = df.drop_duplicates() #put in to avoid duplications down the line.
                              #TODO: needs discussion of how the dups got there in the first place
    return(df)

#select the correct destination types given the level
#NOTE: now selects only for block groups that have positive populations 
def get_dist_df(basedist,level,year):
    df = basedist.copy()
    df = df[df['H7X001']>0]
    if level=='original':
        df = df[df['dest_type']=='polling']         # keep only polling locations
    elif level=='expanded':
        df = df[df['dest_type']!='bg_centroid']     # keep schools and polling locations
    else: #level == full
        df = df                                     #keep everything
    #select the polling locations only for a year
    #keep all other locations 
    #NOTE: this depends strongly on the format of the entries in dest_type and id_dest
    df = df[(df.dest_type != 'polling') | (df.id_dest.str.contains('polling_'.join([str(year)])))]
    return df

##########################
#Other useful constants
##########################

#determines the maximum of the minimum distances
#TODO: Why is this takeing basedist as an input, (which doesn't drop the id_origis with 0 population instead of 
# taking the dist_dfs, which does?)
def get_max_min_dist(basedist):
    min_dist_series = basedist.groupby('id_orig').distance_m.min()
    max_min_dist = min_dist_series.max()
    max_min_dist = math.ceil(max_min_dist) #TODO:Why do we have a ceiling here?
    return max_min_dist

#calculating alpha: \sum(distance_i)/ \sum((distance_i^2)) 
#TODO: Why is the base distance the correct object for this calculation?
def alpha_def(basedist):
    #add a distance square column    
    basedist['distance_squared'] = basedist['distance_m'] * basedist['distance_m']

    distance_sum = basedist['distance_m'].sum()
    distance_sq_sum = basedist['distance_squared'].sum()
    alpha = distance_sum/distance_sq_sum #TODO: This is different than what was original. Check

    #TODO: in the defintion of alpha below, why does the numerator and denominator both have a
    #factor of df3['H7X001'].sum(), aka total population? This will just cancel in the division
        ##calculates the numerator for the alpha value
        #numerator = (df3['H7X001'].sum())*(df3['distance_m'].sum())
        ##calculates the denominator for the alpha value. Incorporates the square list
        #denominator = (df3['H7X001'].sum())*(sum(square_list))
        ##alpha. The aversion to inequality for this sample
        #alpha = numerator/denominator
    return alpha

##########################
#Lists for model variables, constraints, etc.
##########################

#NOTE: In the interest of not constantly changing types, going to keep everything in terms of 
# data frames. If this gets too hairy (aka I hate pandas) will go back to dictionary solutions
#TODO: (SA) Change *_dict functions to *_df and then corresponding code 
# Return dataframe with colums {id_orig, H7X001 (total pop), 'H7X002','H7X003', 'H7X004', 'H7X005', 'H7Z010' 
#                                                                       (2..10 other demographics)}
#TODO: Note, at this point, get_pop_dict and get_id_pop_demographics data can be represented as sub dataframes
#       of dist_df, aka output of get_dist_df. Thus said functions are dropped 
#TODO: original code had a drop duplicate line. Why is this here? and should this just be implemented as
#       unit test? as df.drop_duplicates() appears multiple times in code
#       Is this arising because we are reading multiple years of census data into the same table?
#NOTE: Okay, I'm seeing duplicates. I'd love to know why they are showing up before I just drop them

#NOTE: dist_df is a just a subset of the dataframe given as output of get_dist_df and thus am dropping said function.

#TODO: I think valid_dists is no longer needed by line 77 and 80 of this file

# NOTE: Removing neighborhood_distances to keep from constant type changing
##  in the interest of not Return dictionary {(residential loc, precinct):distance}
## TODO: why is max_min_dist a parameter here? is there a desire to change the max_min
#        distance in as a paremeter to take a subset of pairings in the future?
#def neighborhood_distances(max_min_dist, dataframe):
#    """Return dictionary: {(resident id, precinct_id):distance}
#    """
#    df = valid_dists(dataframe)
#    df = df[df['distance_m']<=max_min_dist].copy() #TODO: Why is this line here? isn't this true by construction? 
#    df['id_tuple'] = list(zip(df.id_orig, df.id_dest))         # add a column with id tuples 
#    return df.set_index('id_tuple')['distance_m'].to_dict()      # generate desired dictionary


#the list of precincts in the neighborhood of each residence
# NOTE: keeping max_min_dist here in case there is a desire to subset pairings by this value. 
def res_precinct_pairings(max_min_dist, dist_df):
    """Return dataframe with colums id_orig, id_dest_list
    """
    #check if the distance of a precinct to the residence is less than min_max_dist. If so, 
    #put it in the list of valid precincts for the residence
    within_radius = dist_df.copy()
    within_radius = within_radius[within_radius.distance_m < max_min_dist]
    within_radius_grouped = within_radius.groupby('id_orig')['id_dest'].apply(list)
    within_radius_grouped.reset_index()
    #within_radius_grouped = within_radius_grouped.rename(columns={'id_dest': 'id_dest_list'}) 
        #TODO: (SA) why does the above line not work?
        #       getting error Series.rename() got an unexpected keyword argument columns
    return within_radius_grouped

#the list of residences in the neighborhood of each precinct
def precinct_res_pairings(max_min_dist, dist_df):
    """Return dataframe wwith colums id_dest, id_orig_list
    """
    #check if the distance of a precinct to the residence is less than min_max_dist. If so, 
    #put it in the list of valid precincts for the residence
    within_radius = dist_df.copy()
    within_radius = within_radius[within_radius.distance_m < max_min_dist]
    within_radius_grouped = within_radius.groupby('id_dest')['id_orig'].apply(list)
    within_radius_grouped.reset_index()
    #within_radius_grouped = within_radius_grouped.rename(columns={'id_orig': 'id_orig_list'}) 
        #TODO: (SA) why does the above line not work?
        #       getting error Series.rename() got an unexpected keyword argument columns
    return within_radius_grouped


##########################
#put quantities of interest into global environment
##########################

#TODO: This is broken. but if I import this this before I import this file
#the config values don't stick around as global variables
from test_config_refactor import *


####dataframes####
basedist = get_base_dist(location, year)
dist_df = get_dist_df(basedist, level, year)

####constants####
alpha = alpha_def(basedist)
global_max_min_dist = get_max_min_dist(basedist)

####Lists####

#list of all possible residence locations with population > 0 (unique)
residences = list(set(dist_df['id_orig']))
#list of all possible precinct locations (unique)
precincts = list(set(dist_df['id_dest']))
#list of unique residence, precint pairs
residence_precinct_pairs = list(itertools.product(residences, precincts)) #TODO: This is needed because dist_df has dups in these pairs?
#set of possible new locations (unique)
#Adding this so that we can limit number of new locations 
new_locations = list(set(dist_df[(dist_df['dest_type']!='polling')]['id_dest']))

####dictionaries####
presincts_in_radius_of_residence = res_precinct_pairings(global_max_min_dist, dist_df)
residences_in_radius_of_precinct = precinct_res_pairings(global_max_min_dist, dist_df)

#TODO: there are features that the model needs that will come from dist_df. 
#This will be implemented in the model file

#######res_prec analysis#########
dist_df['Count'] = 1
res_prec_count = dist_df.groupby(['id_orig', 'id_dest'])["Count"].aggregate('count')
res_prec_count = res_prec_count.to_frame()
res_prec_count = res_prec_count.reset_index()
res_prec_count = res_prec_count.rename(columns= {'distance_m':'Count'})
res_prec_dups = res_prec_count[res_prec_count['Count']==2]
dist_df_count = dist_df.merge(res_prec_count, on = ['id_orig', 'id_dest'], how = 'left')
dups = dist_df_count[dist_df_count['Count']==2]

#Okay, seems to differ only on the initial "unnamed" column. What is this?