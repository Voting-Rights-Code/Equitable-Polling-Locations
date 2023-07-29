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
#TODO: (all) Need to figure out how the distance is calculated and get that implemented at the county level from Google
#     
#TODO: (CR) Need to figure out where the data is going to be stored in the end.


#import modules
import pandas as pd
import math
from decimal import Decimal
import subprocess
import os
import itertools
#from test_config_refactor import * #TODO: (SA) for testing only. remove later
 

##########################
#Data source
#currently assumes that the relevant .csvs are all in the git repo
##########################
#TODO: (CR/SA) fix this when we know where the data is going to be eventually stored
git_dir = subprocess.Popen(['git', 'rev-parse', '--show-toplevel'], stdout=subprocess.PIPE).communicate()[0].rstrip().decode('utf-8')
data_dir = os.path.join(git_dir, 'datasets')

##########################
#Data_file_name dataframe
##########################
#TODO: (SA) This needs to be updated. Currenly only data is for Salem 2016, 2012
#TODO: (all) Do we want to break out different years in to different csvs
file_name_dict = {'Salem':'salem.csv',
                  'Test':'sample.csv',
                  'Gwinett':'Gwinett_GA'}
             
##########################
#change_demographic file names
##########################
#TODO: (SA) This belongs in ingest code
def change_demo_names(df):
    df = df.rename(columns = {'H7X001':'population', 'H7X002':'white', 'H7X003':'black', 
                      'H7X004':'native', 'H7X005':'asian', 'H7Z010':'hispanic'})
    #NOTE: hispanic is an ethnicity, the others are race.Therefore, the sum of the demographic columns
    #will not sum to population
    return(df)

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
def clean_data(location, level, year_list):
    #read in data
    if location not in file_name_dict.keys():
        raise ValueError(f'Do not currently have any data for {location}')
    file_name = file_name_dict[location]
    file_path = os.path.join(data_dir, file_name)
    df = pd.read_csv(file_path, index_col=0)
    #change column names
    if location in {'Salem', 'Test'}:
        df = change_demo_names(df)
    #check year validity
    polling_locations = set(df[df.dest_type == 'polling']['id_dest'])
    for year in year_list:
        if not any(str(year) in poll for poll in polling_locations):
            raise ValueError(f'Do not currently have any data for {location} for {year}')
    #drop duplicates and empty block groups
    df = df.drop_duplicates() #put in to avoid duplications down the line.
    df = df[df['population']>0]
    
    #select data based on level
    if level not in ['original', 'expanded','full']:
        raise ValueError('level must be in {original, expanded,full}')
    if level=='original':
        df = df[df['dest_type']=='polling']         # keep only polling locations
    elif level=='expanded':
        df = df[df['dest_type']!='bg_centroid']     # keep schools and polling locations
    else: #level == full
        df = df   

    #select data based on year
    #select the polling locations only for the indicated years
    #keep all other locations 
    not_polling = df[(df.dest_type != 'polling')]
    polling_year_list =  [df[df.id_dest.str.contains('polling_'.join([str(year)]))] for year in year_list]
    polling_year_list.append(not_polling)
    df = pd.concat(polling_year_list)
    #the concatenation will create duplicates if a polling location is used multiple years
    #drop these
    df = df.drop_duplicates() 
    
    #check that population is unique by id_orig
    pop_df = df.groupby('id_orig')['population'].agg('unique').str.len()
    if any(pop_df>1):
        raise ValueError("Some id_orig has multiple associated populations")

    #create other useful columns
    df['Weighted_dist'] = df['population'] * df['distance_m']    
    return(df)

#select the correct destination types given the level
#NOTE: now selects only for block groups that have positive populations 
def get_dist_df(basedist,level,year):
    df = basedist.copy()
    df = df[df['population']>0]
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
    df['Weighted_dist'] = df['population'] * df['distance_m']

    return df



##########################
#Other useful constants
##########################

#determines the maximum of the minimum distances
#TODO: Why is this takeing basedist as an input, (which doesn't drop the id_origis with 0 population instead of 
# taking the dist_dfs, which does?)
def get_max_min_dist(dist_df):
    min_dist = dist_df[['id_orig', 'distance_m']].groupby('id_orig').agg('min')
    max_min_dist = min_dist.distance_m.max()
    max_min_dist = math.ceil(max_min_dist)
    return max_min_dist

def alpha_all(df):
    #add a distance square column    
    df['distance_squared'] = df['distance_m'] * df['distance_m']

    #population weighted distances
    distance_sum = sum(df['population'] * df['distance_m'])
    #population weighted distance squared
    distance_sq_sum = sum(df['population']*df['distance_squared'])
    alpha = distance_sum/distance_sq_sum 
    return alpha


def alpha_min(df):
    #Find the minimal distance to polling location
    min_df= df[['id_orig', 'distance_m','population']].groupby('id_orig').agg('min')

    #find the square of the min distances
    min_df['distance_squared'] = min_df['distance_m'] * min_df['distance_m']  
    #population weighted distances
    distance_sum = sum(min_df['population']*min_df['distance_m'])
    #population weighted distance squared
    distance_sq_sum = sum(min_df['population']*min_df['distance_squared'])
    alpha = distance_sum/distance_sq_sum 
    return alpha

def alpha_mean(df):
    #Find the mean distance to polling location
    mean_df = df[['id_orig', 'distance_m', 'population']].groupby('id_orig').agg('mean')
    
    #find the square of the min distances
    mean_df['distance_squared'] = mean_df['distance_m'] * mean_df['distance_m']  
    #population weighted distances
    distance_sum = sum(mean_df['population']*mean_df['distance_m'])
    #population weighted distance squared
    distance_sq_sum = sum(mean_df['population']*mean_df['distance_squared'])
    alpha = distance_sum/distance_sq_sum 
    return alpha