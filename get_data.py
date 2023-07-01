#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Wed 27 Oct 2021

@author: murrell

This module returns sample precinct and residence data for use in Pyomo models.

Functions:
    get_base_dist()
    get_precinct_ids()
    get_gas_ids()
    get_residence_ids()
    get_id_pop_dict()
    get_distances()
"""

#import modules
import pandas as pd
import math
import os
from collections import defaultdict

#returns dataframe of distances for the original case. This is to keep alpha constant amongst all cases
def get_basedist(dist, city,year):
    file_path = os.path.join('datasets', dist)
    df = pd.read_csv(file_path)
    df = df[df['city']==city]
    df = df[df['dest_type']=='polling']        # keep only polling locations
    #for i in range(0,len(df['id_dest']):
     #   if year == 2012:
      #      if df.id_dest.str.contains(
    if year == '2012':
        df = df[~df.id_dest.str.contains('|'.join(['poll_2016']))]
    if year == '2016':
        df = df[~df.id_dest.str.contains('|'.join(['poll_2012']))]
    df = df.sort_index()
    return df

#returns the distance dataframe for the given city and year
def get_dist_df(dist,city,level, year):
    file_path = os.path.join('datasets', dist)
    df = pd.read_csv(file_path)
    df = pd.read_csv(dist)
    df = df[df['city']==city]
    if level=='original':
        df = df[df['dest_type']=='polling']        # keep only polling locations
        df = df.sort_index()
    if level=='expanded':
        df = df[df['dest_type']!='bg_centroid']        # keep schools and polling locations
        df = df.sort_index()
    if year == '2012':
        df = df[~df.id_dest.str.contains('|'.join(['poll_2016']))]
    if year == '2016':
        df = df[~df.id_dest.str.contains('|'.join(['poll_2012']))]
    df = df.sort_index()
    return df

# Return list of residential locations with population > 0
def get_residential_ids(dataframe):
    """Return a list of ids of residential locations with positive populations."""
      # read in as dataframe
    df = dataframe
    df = df[df['H7X001']>0].copy()         # keep only populated locations
    return list(df['id_orig'])          # return the ids as a list

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