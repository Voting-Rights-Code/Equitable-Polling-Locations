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
from collections import defaultdict


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
#pull out relevant data for models
##########################
#returns dataframe of distances for the original case. This is to keep alpha constant amongst all cases
#TODO: originally, this function added a suffix of _year_num to locations tagged as poll. 
#       but this is currently in the column id_dest. Therefore not contained in this function
#TODO: How should I understand the id_dest poll_year_num. Does this involve multiplicity? I.e. if the same location is a polling
#       location in mulltiple years, does it show up twice, once as poll_year1_num1 and again as poll_year2_num2?
def get_base_dist(location, year):
    if location not in file_name_dict.keys():
        raise ValueError(f'Do not currently have any data for {location}')
    file_name = file_name_dict[location]
    file_path = os.path.join(data_dir, file_name)
    df = pd.read_csv(file_path)
    #extract years
    polling_locations = set(df[df.id_dest.str.contains('poll')])
    year_set = set(poll[5:9] for poll in polling_locations)
    if str(year) not in year_set:
        raise ValueError(f'Do not currently have any data for {location} for {year}')
    return(df)

#select the correct destination types given the level
def get_dist_df(basedist,level,year):
    df = basedist.copy()
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

# Return list of residential locations with population > 0
# TODO: Does pyomo want variables entered as lists?
def get_residential_ids(dist_df):
    """
    Input: data frame returned from get_dist_df
    Output: a list of ids of residential locations with positive populations."""
    return list(dist_df[dist_df['H7X001']>0]['id_orig'])         

###########
#Start here
###########

# Return dictionary {location id, population}
def get_id_pop_dict(dataframe):
    """Return dictionary: {residential location id: (nonzero) population}"""
    df = dataframe  # read in as dataframe
    df = df[df['H7X001']>0]                # keep only populated locations
    return df.set_index('id_orig')['H7X001'].to_dict()  #id:population

#returns dataframe of demographic populations and the respective census block
def get_pop_demographics(dataframe):
    """Return dictionary: {residential location id: (nonzero) population}"""
    df=dataframe
    df = df[df['H7X001']>0]                # keep only populated locations
    df = df.loc[:,['id_orig','H7X001','H7X002','H7X003', 'H7X004', 'H7X005', 'H7Z010']] 
    df = df.drop_duplicates()
    return df  


#set of all possible precinct locations
def get_precinct_ids(dataframe):
    """Return a list of ids of precinct locations."""
    df = dataframe  # read in as dataframe
    valid_ids = set(df['id_dest'])
    return list(valid_ids) 

##### Adding this so that we can limit number of new locations #####
#set of possible new locations
def get_new_location_ids(dataframe):
    """Return a list of ids of schools + bg_centeroids in distance df """
    df = dataframe  # read in as dataframe
    valid_ids = set(df[(df['dest_type']!='polling')]['id_dest'])
    return list(valid_ids)

#determines the maximum of the minimum distances
def get_max_min_dist(basedist):
    df = basedist
    df['id_tuple'] = list(zip(df.id_orig, df.id_dest)) 
    distance_df = df.set_index('id_tuple')['distance_m'].to_dict() 
    distance_df = [{'id_orig':a, 'id_dest':b, 'dist':c} for (a,b),c in distance_df.items()]
    df_dist = pd.DataFrame(distance_df)
    df2 = df_dist.groupby('id_orig').dist.min().reset_index()
    max_min_dist = df2.dist.max()
    max_min_dist = math.ceil(max_min_dist)
    return max_min_dist

#dataframe of just census blocks, loctions, and distances between the two
def dist_df(dataframe):
    df = dataframe
    df = df.loc[:,['id_orig','id_dest','distance_m']]
    return df

#some of the residences in the distance file do not appear in the population file
def valid_dists(dataframe): 
    """Return dictionary: {(res, precinct):dist
    """
    df= dataframe
    pop_df = df[df['H7X001']>0]
    valid_ids = set(pop_df['id_orig'])
    dff= pd.DataFrame(dist_df(dataframe))
    dff_ids = set(dff['id_orig'])
    drop_ids = []
    for c in dff.index:
        if dff['id_orig'][c] not in valid_ids:
            drop_ids.append(c)
    drop_df = pd.DataFrame(drop_ids)
    dff.drop(drop_ids, inplace = True)
    return dff

# Return dictionary {(residential loc, precinct):distance}
def neighborhood_distances(max_min_dist, dataframe):
    """Return dictionary: {(resident id, precinct_id):distance}
    """
    df = valid_dists(dataframe)
    df = df[df['distance_m']<=max_min_dist].copy()
    df['id_tuple'] = list(zip(df.id_orig, df.id_dest))         # add a column with id tuples 
    return df.set_index('id_tuple')['distance_m'].to_dict()      # generate desired dictionary


#the list of precincts in the neighborhood of each residence
def res_precinct_pairings(max_min_dist, dataframe):
    """Return dictionary: {residence:[precincts]}
    """
    res_precinct_dict = defaultdict(list) #list of precincts
    for c,s in neighborhood_distances(max_min_dist, dataframe).keys():
        res_precinct_dict[c].append(s)
    return res_precinct_dict

#the list of residences in the neighborhood of each precinct
def precinct_res_pairings(max_min_dist, dataframe):
    """Return dictionary: {residence:[precincts]}
    """
    precinct_res_dict = defaultdict(list) #list of precincts
    for c,s in neighborhood_distances(max_min_dist, dataframe).keys():
        precinct_res_dict[s].append(c)
    return precinct_res_dict

#calculating alpha 
def alpha_def(max_min_dist, basedist):
    df = basedist
    df3 = df.loc[:,['id_orig','id_dest','distance_m', 'H7X001']]

    #establishes the squared value for each distance. This will be later used in the denominator
    square_list = []
    for d in df3.index:
        square_list.append(df3['distance_m'][d]**2)

    #calculates the numerator for the alpha value
    numerator = (df3['H7X001'].sum())*(df3['distance_m'].sum())

    #calculates the denominator for the alpha value. Incorporates the square list
    denominator = (df3['H7X001'].sum())*(sum(square_list))

    #alpha. The aversion to inequality for this sample
    alpha = numerator/denominator
    return alpha