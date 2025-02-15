#######################################
#Created on 6 December 2023
#
#@author: Voting Rights Code
#@attribution: based off of code by Josh Murell
#######################################

import pandas as pd
import numpy as np
import math
import os
from haversine import haversine
import geopandas as gpd
from model_config import PollingModelConfig
from pull_census_data import pull_census_data

from constants import DATASETS_DIR


#define columns for each input data set
LOCATIONS_COLS = [
    'Location',
    'Address',
    'Location type',
    'Lat, Long',
]

# Prefix to add to Shape files to join with demographic data.
GEO_ID_PREFIX = '1000000US'

P3_COLUMNS = [
    'GEO_ID',
    'NAME',
    'P3_001N', # Total population
    'P3_003N', # White alone
    'P3_004N', # Black or African American alone
    'P3_005N', # American Indian or Alaska Native alone
    'P3_006N', # Asian alone
    'P3_007N', # Native Hawaiian and Other Pacific Islander alone
    'P3_008N', # Some other race alone
    'P3_009N', # Two or More Races
]

P4_COLUMNS = [
    'GEO_ID',
    'NAME',
    'P4_001N', # Total population
    'P4_002N', # Total hispanic
    'P4_003N', # Total non_hispanic
]

BLOCK_SHAPE_COLS = [
    'GEOID20',
    'INTPTLAT20',
    'INTPTLON20',
]

BLOCK_GROUP_SHAPE_COLS = [
    'GEOID20',
    'INTPTLAT20',
    'INTPTLON20',
]


##########################
#read in data and write relevant dataframe for model to file
##########################
#build distance data set from census data and potential pollig location data.
#using driving distances if driving = True

def build_source(config: PollingModelConfig, log):
    ######
    #Pull out necessary config variables
    ######
    location = config.location
    driving = config.driving
    log_distance = config.log_distance

    ######
    #Check that necessary files exist
    ######
    #1. Potential polling locations
    file_name = location + '_locations_only.csv'
    location_source_file = os.path.join(DATASETS_DIR, 'polling', location, file_name)
    if os.path.exists(location_source_file):
        #warnings.warn(f'{file_name} found. Last modified {os.path.getmtime(LOCATION_SOURCE_FILE)}.')
        locations = pd.read_csv(location_source_file)
    else:
        raise ValueError(f'Potential polling location data ({location_source_file}) not found.')

    #2. Census demographic data
    file_nameP3 = 'DECENNIALPL2020.P3-Data.csv'
    file_nameP4 = 'DECENNIALPL2020.P4-Data.csv'
    demographics_dir = os.path.join(DATASETS_DIR, 'census', 'redistricting', location)
    P3_SOURCE_FILE  = os.path.join(demographics_dir, file_nameP3)
    P4_SOURCE_FILE  = os.path.join(demographics_dir, file_nameP4)
    if not os.path.exists(demographics_dir):
        statecode = location[-2:]
        locality = location[:-3].replace('_',' ')
        pull_census_data(statecode, locality)
    if os.path.exists(P3_SOURCE_FILE):
        p3_df = pd.read_csv(P3_SOURCE_FILE,
            header=[0,1], # DHC files have two headers rows when exported to CSV - tell pandas to take top one
            low_memory=False, # files are too big, set this to False to prevent errors
            )
    else:
        raise ValueError(f'Census data from table P3 not found. Download using api or manually following download instruction from README.')
    if os.path.exists(P4_SOURCE_FILE):
        p4_df = pd.read_csv(P4_SOURCE_FILE,
            header=[0,1], # DHC files have two headers rows when exported to CSV - tell pandas to take top one
            low_memory=False, # files are too big, set this to False to prevent errors
            )
    else:
        raise ValueError(f'Census data from table P4 not found. Download using api or manually following download instruction from README.')

    #3. Census geographic data
    geography_dir = os.path.join(DATASETS_DIR, 'census', 'tiger', location)
    file_list = os.listdir(geography_dir)
    file_name_block = [f for f in file_list if f.endswith('tabblock20.shp')][0]
    file_name_bg = [f for f in file_list if f.endswith('bg20.shp')][0]
    block_source_file  = os.path.join(geography_dir, file_name_block)
    block_group_source_file  = os.path.join(geography_dir, file_name_bg)
    if os.path.exists(block_source_file):
        blocks_gdf = gpd.read_file(block_source_file)
    else:
        raise ValueError(f'Census data for block geography not found. Reinstall using api or manually following download instruction from README.')
    if os.path.exists(block_group_source_file):
        blockgroup_gdf = gpd.read_file(block_group_source_file)
    else:
        raise ValueError(f'Census data for block group geography not found. Reinstall using api or manually following download instruction from README.')

    #######
    #Clean data
    #######

    #select columns for each data set
    locations = locations[LOCATIONS_COLS]
    p3_df.columns=[multicols[0] for multicols in p3_df.columns]
    p3_df = p3_df[P3_COLUMNS]
    p4_df.columns=[multicols[0] for multicols in p4_df.columns]
    p4_df = p4_df[P4_COLUMNS]
    blocks_gdf = blocks_gdf[BLOCK_SHAPE_COLS]
    blockgroup_gdf = blockgroup_gdf[BLOCK_GROUP_SHAPE_COLS]

    #####
    #Make a demographics table
    #####
    #combine P3 and P4 data to make a joint demographics set
    demographics = p4_df.merge(p3_df, left_on=['GEO_ID', 'NAME'], right_on=['GEO_ID', 'NAME'],how = 'outer')

    #Consistency check for the data pull
    demographics['Pop_diff'] = demographics.P4_001N-demographics.P3_001N
    if demographics.loc[demographics.Pop_diff != 0].shape[0]!=0:
        raise ValueError('Populations different in P3 and P4. Are both pulled from the voting age universe?')

    #Change column names
    demographics.drop(['P4_001N', 'Pop_diff'], axis =1, inplace = True)
    demographics = demographics.rename(columns = {'P4_002N': 'hispanic', 'P4_003N':'non_hispanic', 'P3_001N':'population', 'P3_003N':'white', 'P3_004N':'black', 'P3_005N':'native', 'P3_006N':'asian', 'P3_007N':'pacific_islander', 'P3_008N':'other', 'P3_009N':'multiple_races'})

    #drop geo_id_prefix
    demographics['GEO_ID'] = demographics['GEO_ID'].str.replace(GEO_ID_PREFIX, '')

    #join with block group shape files
    demographics_block = demographics.merge(blocks_gdf, left_on='GEO_ID', right_on = 'GEOID20',how='left')

    #make lat/ long floats
    demographics_block.INTPTLAT20 = demographics_block.INTPTLAT20.astype(float)
    demographics_block.INTPTLON20 = demographics_block.INTPTLON20.astype(float)

    #drop duplicates and empty block groups
    demographics_block = demographics_block.drop_duplicates() #put in to avoid duplications down the line.
    demographics_block = demographics_block[demographics_block['population']>0]
    
    #####
    #Make a polling locations table (including block group centroid)
    #####

    #the potential locations data needs further processing:
    #1. add a destination type column
    locations['dest_type'] = 'polling'
    locations['dest_type'].mask(locations['Location type'].str.contains('Potential'), 'potential', inplace=True)

    #2. change the lat, long into two columns
    locations[['Latitude', 'Longitude']] = locations['Lat, Long'].str.split(pat = ', ', expand=True).astype(float)
    locations.drop(['Lat, Long'], axis =1, inplace = True)

    #The block group needs to be processed to match the potential location table
    blockgroup_gdf = blockgroup_gdf.rename(columns = {'GEOID20': 'Location', 'INTPTLAT20':'Latitude', 'INTPTLON20':'Longitude'})
    blockgroup_gdf['Address'] = None
    blockgroup_gdf['Location type'] = 'bg_centroid'
    blockgroup_gdf['dest_type'] = 'bg_centroid'

    #Concatenate
    all_locations = pd.concat([locations, blockgroup_gdf])

    #Lat and Long current mix of string and geometry. Make them all floats
    all_locations['Latitude'] = pd.to_numeric(all_locations['Latitude'])
    all_locations['Longitude'] = pd.to_numeric(all_locations['Longitude'])

    if len(all_locations.Location) != len(set(all_locations.Location)):
        raise ValueError('Non-unique names in Location column. This will cause errors later.')

    #####
    # Cross join polling locations and demographics tables 
    #####
    full_df = demographics_block.merge(all_locations, how= 'cross')
    

    #####
    #Rename, select columns
    #####
    full_df = full_df.rename(columns = {'GEO_ID': 'id_orig', 'Address': 'address', 'Latitude':'dest_lat', 'Longitude':'dest_lon', 'INTPTLAT20':'orig_lat', 'INTPTLON20':'orig_lon', 'Location type': 'location_type', 'Location': 'id_dest'})

    FULL_DF_COLS = [
    'id_orig',
    'id_dest',
    'address',
    'dest_lat',
    'dest_lon',
    'orig_lat',
    'orig_lon',
    'location_type',
    'dest_type',
    'population',
    'hispanic',
    'non_hispanic',
    'white',
    'black',
    'native',
    'asian',
    'pacific_islander',
    'other',
    'multiple_races',
    ]

    full_df = full_df[FULL_DF_COLS]

    #####
    # Calculate appropriate distance
    #####

    if not driving:
        full_df['distance_m'] = full_df.apply(lambda row: haversine((row.orig_lat, row.orig_lon), (row.dest_lat, row.dest_lon)), axis=1)*1000
        full_df['source'] = 'haversine distance'
    else: # driving is true
        driving_file_name = location + '_driving_distances.csv'
        DRIVING_DISTANCES_FILE = os.path.join(DATASETS_DIR, 'driving', location, driving_file_name)
        full_df = insert_driving_distances(full_df, DRIVING_DISTANCES_FILE, log)
        full_df['source'] = 'driving distance'
    #if log distance, modify the source and distance columns
    if log_distance:
        full_df['source'] = 'log ' + full_df['source']
        #TODO: why are there 0 distances showing up?
        full_df['distance_m'].mask(full_df['distance_m'] == 0.0, 0.001, inplace=True)
        full_df['distance_m'] = np.log(full_df['distance_m'])


    #####
    #reformat and write to file
    #####

    full_df['id_orig'] = full_df['id_orig'].astype(str)
    full_df['id_dest'] = full_df['id_dest'].astype(str)

    if not driving:
        output_file_name = location + '.csv'
    else: #driving is true
        output_file_name = location + '_driving.csv'
    if log_distance:
        output_file_name = output_file_name.replace('.csv', '_log.csv')

    output_path = os.path.join(DATASETS_DIR, 'polling', location, output_file_name)
    full_df.to_csv(output_path, index = True)
    return


def insert_driving_distances(df: pd.DataFrame, driving_distance_file_path: str, log: bool=False) -> pd.DataFrame:
    '''
    Given a dataframe with origin and destination ids, update the distance_m column
    with driving distances in the given driving distance file. If distance_m exists in df, it
    will be renamed haversine_m.

    Arguments
    df: A pandas DataFrame that contains id_orig and id_dest
    driving_distance_file_path: the path to a file that contains a driving distance for each
                                origin/destination pair. Each line will be of the form
                                id_orig, id_dest, distance_m. This file must contain a distance
                                for every possible origin/destination pair.
    log: boolean - True if verbose

    Raises
    ValueError - if anything goes wrong (missing file, bad format, missing data)

    Returns
    The original dataframe with the distance_m column populated with the driving distances.

    '''
    if log:
        print(f'inserting driving distances {driving_distance_file_path}')
    if os.path.exists(driving_distance_file_path):
        driving_distance = pd.read_csv(driving_distance_file_path)
        driving_distance['id_orig'] = driving_distance.id_orig.astype(str)
    else:
        raise ValueError(f'Driving Distance File ({driving_distance_file_path}) not found.')
    if {'id_orig', 'id_dest', 'distance_m'} - set(driving_distance.columns):
        raise ValueError(f'Driving Distance File ({driving_distance_file_path}) '
                         'must contain id_orig, id_dest, and distance_m columns')

    combined_df = pd.merge(df, driving_distance, on=['id_orig', 'id_dest'], how='left')


    return combined_df

#########
#Read the intermediate data frame from file, and pull the relevant rows
#Note this this function is called twice, once for calculating alpha and once for
#the base data set.
#The call for alpha should only take the original polling locations.#########
#########

def clean_data(config: PollingModelConfig, for_alpha: bool, log: bool):
    location = config.location
    year_list = config.year
    driving = config.driving
    log_distance = config.log_distance

    #read in data
    file_path = os.path.join(DATASETS_DIR, 'polling', location, f'{location}.csv')
    if driving:
        file_path = file_path.replace('.csv', '_driving.csv')
    if log_distance:
        file_path = file_path.replace('.csv', '_log.csv')

    if not os.path.isfile(file_path):
        raise ValueError(f'Do not currently have any data for {file_path} from {config.config_file_path}')
    df = pd.read_csv(file_path, index_col=0)
    df= df.astype({'id_orig':'str'})

    #pull out unique location types is this data
    unique_location_types = df['location_type'].unique()

    if for_alpha:
        bad_location_list = [location_type for location_type in unique_location_types if 'Potential' in location_type or 'centroid' in location_type]
    else:
        bad_location_list = config.bad_types

    polling_location_types = set(df[df.dest_type == 'polling']['location_type'])
    for year in year_list:
        if not any(str(year) in poll for poll in polling_location_types):
            raise ValueError(f'Do not currently have any data for {location} for {year} from {config.config_file_path}')
    

    #exclude bad location types
    # The bad types must be valid location types
    if not set(bad_location_list).issubset(set(unique_location_types)):
        raise ValueError(f'unrecognized bad location types types {set(bad_location_list).difference(set(unique_location_types))} in {config.config_file_path}' )
    #drop rows of bad location types in df
    df = df[~df['location_type'].isin(bad_location_list)]

    #select data based on year
    #select the polling locations only for the indicated years
    #keep all other locations
    df['dest_type'].mask(df['dest_type'] != 'bg_centroid', 'potential', inplace = True)
    df['dest_type'].mask(df['location_type'].str.contains('|'.join(year_list)), 'polling', inplace = True)
    #check that this hasn't created duplicates (should not have); drop these
    df = df.drop_duplicates()

    #check that population is unique by id_orig
    pop_df = df.groupby('id_orig')['population'].agg('unique').str.len()
    if any(pop_df>1):
        raise ValueError(f"Some id_orig has multiple associated populations from {config.config_file_path}")

    # raise error if there are any missing distances
    if len(df[pd.isnull(df.distance_m)]) > 0:
        if log:
            # indicate destinations and origins that are missing driving distances
            all_orig = set(df.id_orig)
            all_dest = set(df.id_dest)
            notna_df = df[pd.notna(df.distance_m)]
            notna_orig = set(notna_df.id_orig)
            notna_dest = set(notna_df.id_dest)
            missing_sources = all_orig - notna_orig
            missing_dests = all_dest - notna_dest
            if len(missing_dests) > 0:
                print(f'{len(missing_dests)} missing dests in driving distances: {missing_dests}')
            if len(missing_sources) > 0:
                print(f'{len(missing_sources)} missing orig in driving distances: {missing_sources}')
        raise ValueError(f'Driving Distance File ({file_path}) '
                         'does not contain driving distances for all id_orig/id_dest pairs.')

    
    #create other useful columns
    df['Weighted_dist'] = df['population'] * df['distance_m']
    return(df)

##########################
#Other functions for data processing
##########################

#determines the maximum of the minimum distances
def get_max_min_dist(dist_df):
    min_dist = dist_df[['id_orig', 'distance_m']].groupby('id_orig').agg('min')
    max_min_dist = min_dist.distance_m.max()
    max_min_dist = math.ceil(max_min_dist)
    return max_min_dist

#various alpha function. Really only use alpha_min
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
