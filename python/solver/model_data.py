#######################################
#Created on 6 December 2023
#
#@author: Voting Rights Code
#@attribution: based off of code by Josh Murell
#######################################

from dataclasses import dataclass
from typing import Literal

import pandas as pd
import numpy as np
import math
import os
from haversine import haversine
import geopandas as gpd

from python.database import query
from python.utils import (
    build_driving_distances_file_path,
    build_locations_only_file_path,
    build_locations_distance_file_path,
    build_demographics_dir_path,
    build_p3_source_file_path,
    build_p4_source_file_path,
    is_int,
)

from python.utils.constants import LOCATION_SOURCE_DB
from python.utils.pull_census_data import pull_census_data
from python.utils import get_block_source_file_path, get_block_group_block_source_file_path
from .model_config import PollingModelConfig

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

@dataclass
class PollingLocationsOnlyResult:
    locations_only: pd.DataFrame
    polling_locations_only_set_id: str = None
    output_path: str = None

def get_polling_locations_only(
        location_source: Literal['db', 'csv'],
        location: str,
        locations_only_path_override: str = None,
) -> PollingLocationsOnlyResult:
    location_only_set_id: str = None
    if location_source == LOCATION_SOURCE_DB:
        location_only_set = query.get_location_only_set(location)
        if not location_only_set:
            raise ValueError(f'Could not find location only set for {location} in the database.')

        location_only_set_id = location_only_set.id
        locations_only_df = query.get_locations_only(location_only_set_id)

        # Rename databas columns to match csv columns
        locations_only_df = locations_only_df.rename(
            {
                'location': 'Location',
                'address': 'Address',
                'location_type': 'Location type',
                'lat_lon': 'Lat, Long',
            }, axis=1)

        if locations_only_df.empty:
            raise ValueError(f'No locations only for locations only set {location} id {location_only_set.id}.')


    else:
        if locations_only_path_override:
            # If a path override is provided, use that instead of the default file path
            locations_only_source_file = locations_only_path_override
        else:
            locations_only_source_file = build_locations_only_file_path(location)

        if os.path.exists(locations_only_source_file):
            #warnings.warn(f'{file_name} found. Last modified {os.path.getmtime(LOCATION_SOURCE_FILE)}.')
            locations_only_df = pd.read_csv(locations_only_source_file)
        else:
            raise ValueError(f'Potential polling location data ({locations_only_source_file}) not found.')


    locations_only_df = locations_only_df[LOCATIONS_COLS]

    #the potential locations data needs further processing:
    #1. add a destination type column
    locations_only_df['dest_type'] = 'polling'
    locations_only_df['dest_type'].mask(locations_only_df['Location type'].str.contains('Potential'), 'potential', inplace=True)

    #2. change the lat, long into two columns
    locations_only_df[['Latitude', 'Longitude']] = locations_only_df['Lat, Long'].str.split(pat = ', ', expand=True).astype(float)
    locations_only_df.drop(['Lat, Long'], axis =1, inplace = True)

    return PollingLocationsOnlyResult(
        locations_only=locations_only_df,
        polling_locations_only_set_id=location_only_set_id,
    )


def get_blocks_gdf(census_year: str, location: str) -> gpd.GeoDataFrame:
    block_source_file = get_block_source_file_path(census_year, location)
    blocks_gdf = gpd.read_file(block_source_file)

    blocks_gdf = blocks_gdf[BLOCK_SHAPE_COLS]

    return blocks_gdf


def get_blockgroup_gdf(census_year: str, location: str) -> gpd.GeoDataFrame:
    block_group_source_file = get_block_group_block_source_file_path(census_year, location)
    blockgroup_gdf = gpd.read_file(block_group_source_file)

    blockgroup_gdf = blockgroup_gdf[BLOCK_GROUP_SHAPE_COLS]

    #The block group needs to be processed to match the potential location table
    # pylint: disable-next=line-too-long
    blockgroup_gdf = blockgroup_gdf.rename(columns = {'GEOID20': 'Location', 'INTPTLAT20':'Latitude', 'INTPTLON20':'Longitude'})
    blockgroup_gdf['Address'] = None
    blockgroup_gdf['Location type'] = 'bg_centroid'
    blockgroup_gdf['dest_type'] = 'bg_centroid'

    return blockgroup_gdf


def get_demographics_block(census_year: str, location: str) -> pd.DataFrame:
    ''' Combine the P3 and P4 census data to generate demographic block data for a specific location and census year. '''

    demographics_dir = build_demographics_dir_path(location)
    p3_source_file = build_p3_source_file_path(census_year, location)
    p4_source_file = build_p4_source_file_path(census_year, location)

    if not os.path.exists(demographics_dir):
        statecode = location[-2:]
        locality = location[:-3].replace('_',' ')
        pull_census_data(statecode, locality)

    if os.path.exists(p3_source_file):
        p3_df = pd.read_csv(p3_source_file,
            header=[0,1], # DHC files have two headers rows when exported to CSV - tell pandas to take top one
            low_memory=False, # files are too big, set this to False to prevent errors
            )
    else:
        # pylint: disable-next=line-too-long
        raise ValueError(f'Census data from table P3 not found. Download using api or manually following download instruction from README. {p3_source_file}')

    if os.path.exists(p4_source_file):
        p4_df = pd.read_csv(p4_source_file,
            header=[0,1], # DHC files have two headers rows when exported to CSV - tell pandas to take top one
            low_memory=False, # files are too big, set this to False to prevent errors
            )
    else:
        # pylint: disable-next=line-too-long
        raise ValueError('Census data from table P4 not found. Download using api or manually following download instruction from README.')

    #3. Census geographic data
    block_source_file = get_block_source_file_path(census_year, location)
    blocks_gdf = gpd.read_file(block_source_file)

    block_group_source_file = get_block_group_block_source_file_path(census_year, location)
    blockgroup_gdf = gpd.read_file(block_group_source_file)

    #######
    #Clean data
    #######
    print('Cleaning data')
    #select columns for each data set
    p3_df.columns=[multicols[0] for multicols in p3_df.columns]
    p3_df = p3_df[P3_COLUMNS]
    p4_df.columns=[multicols[0] for multicols in p4_df.columns]
    p4_df = p4_df[P4_COLUMNS]
    # blockgroup_gdf = blockgroup_gdf[BLOCK_GROUP_SHAPE_COLS]

    #####
    #Make a demographics table
    #####
    print('Making demographics table')
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

    blocks_gdf = get_blocks_gdf(census_year, location)

    #join with block group shape files
    demographics_block = demographics.merge(blocks_gdf, left_on='GEO_ID', right_on = 'GEOID20',how='left')

    #make lat/ long floats
    demographics_block.INTPTLAT20 = demographics_block.INTPTLAT20.astype(float)
    demographics_block.INTPTLON20 = demographics_block.INTPTLON20.astype(float)

    #drop duplicates and empty block groups
    demographics_block = demographics_block.drop_duplicates() #put in to avoid duplications down the line.
    demographics_block = demographics_block[demographics_block['population']>0]

    return demographics_block


@dataclass
class BuildSourceResult:
    location_source: Literal['db', 'csv']
    census_year: str
    location: str
    driving: bool
    log_distance: bool
    map_source_date: str = None,
    output_path: str = None
    driving_distance_set_id: str = None
    polling_locations_only_set_id: str = None

##########################
#read in data and write relevant dataframe for model to file
##########################
#build distance data set from census data and potential pollig location data.
#using driving distances if driving = True

def build_source(
    location_source: Literal['db', 'csv'],
    census_year: str,
    location: str,
    driving: bool,
    log_distance: bool,
    map_source_date: str = None,
    log: bool = False,
    locations_only_path_override: str = None,
    output_path_override: str = None,
) -> BuildSourceResult:
    locations_only_results = get_polling_locations_only(location_source, location, locations_only_path_override)
    locations_only_df = locations_only_results.locations_only

    if not is_int(census_year):
        raise ValueError(f'Invalid Census year {census_year} for location {location}')

    if not output_path_override:
        output_path = build_locations_distance_file_path(census_year, location, driving, log_distance)
    else:
        output_path = output_path_override

    result = BuildSourceResult(
        location_source=location_source,
        census_year=census_year,
        location=location,
        driving=driving,
        log_distance=log_distance,
        map_source_date=map_source_date,
        polling_locations_only_set_id=locations_only_results.polling_locations_only_set_id,
        output_path=output_path
    )

    #####
    #Make a polling locations table (including block group centroid)
    #####
    blockgroup_gdf = get_blockgroup_gdf(census_year, location)

    #Concatenate
    all_locations = pd.concat([locations_only_df, blockgroup_gdf])

    #Lat and Long current mix of string and geometry. Make them all floats
    all_locations['Latitude'] = pd.to_numeric(all_locations['Latitude'])
    all_locations['Longitude'] = pd.to_numeric(all_locations['Longitude'])

    if len(all_locations.Location) != len(set(all_locations.Location)):
        raise ValueError('Non-unique names in Location column. This will cause errors later.')

    #####
    # Cross join polling locations and demographics tables
    #####
    demographics_block_df = get_demographics_block(census_year, location)
    full_df = demographics_block_df.merge(all_locations, how= 'cross')

    #####
    #Rename, select columns
    #####
    print('renaming and selecting columns')
    # pylint: disable-next=line-too-long
    full_df = full_df.rename(columns = {'GEO_ID': 'id_orig', 'Address': 'address', 'Latitude':'dest_lat', 'Longitude':'dest_lon', 'INTPTLAT20':'orig_lat', 'INTPTLON20':'orig_lon', 'Location type': 'location_type', 'Location': 'id_dest'})
    full_df = full_df[FULL_DF_COLS]
    
    #####
    # Calculate appropriate distance
    #####
    print('calculating distances')    
    if driving:
        if location_source == LOCATION_SOURCE_DB:
            driving_distance_set = query.find_driving_distance_set(census_year, map_source_date, location)
            if not driving_distance_set:
                # pylint: disable-next=line-too-long
                raise ValueError('DrivingDistance set not found in database for census_year {census_year}, map_source_date {map_source_date}, location {location}.')
            result.driving_distance_set_id = driving_distance_set.id
            driving_distances_df = get_db_driving_distances(driving_distance_set.id)
        else:
            driving_distances_df = get_csv_driving_distances(census_year, map_source_date, location)
        
        full_df = insert_driving_distances(full_df, driving_distances_df)
    else:
        # pylint: disable-next=line-too-long
        print('calculate haversine distance')
        full_df['distance_m'] = full_df.apply(lambda row: haversine((row.orig_lat, row.orig_lon), (row.dest_lat, row.dest_lon)), axis=1)*1000
        full_df['source'] = 'haversine distance'

    #if log distance, modify the source and distance columns
    if log_distance:
        full_df['source'] = 'log ' + full_df['source']
        #TODO: why are there 0 distances showing up?
        print('calculate log distance')
        full_df['distance_m'].mask(full_df['distance_m'] == 0.0, 0.001, inplace=True)
        full_df['distance_m'] = np.log(full_df['distance_m'])

    #####
    #reformat and write to file
    #####
    print('reformating and writing to file')
    full_df['id_orig'] = full_df['id_orig'].astype(str)
    full_df['id_dest'] = full_df['id_dest'].astype(str)
    
    full_df.to_csv(output_path, index = True)
    return result


def insert_driving_distances(
    source_df: pd.DataFrame,
    driving_distances_df: pd.DataFrame,
) -> pd.DataFrame:
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

    if {'id_orig', 'id_dest', 'distance_m'} - set(driving_distances_df.columns):
        raise ValueError('Driving Distances must contain id_orig, id_dest, and distance_m columns')

    combined_df = pd.merge(source_df, driving_distances_df, on=['id_orig', 'id_dest'], how='left')

    combined_df['source'] = 'driving distance'
    return combined_df


def get_csv_driving_distances(census_year: str, map_source_date: str, location: str) -> pd.DataFrame:
    driving_distance_file_path = build_driving_distances_file_path(census_year, map_source_date, location)
    if not os.path.exists(driving_distance_file_path):
        raise ValueError(f'Driving Distance File ({driving_distance_file_path}) not found.')

    return load_driving_distances_csv(driving_distance_file_path)

def get_db_driving_distances(driving_distance_set_id: str) -> pd.DataFrame:
    driving_distances = query.get_driving_distances(driving_distance_set_id)
    if driving_distances.empty:
        raise ValueError(f'No driving distances for distance set {driving_distance_set_id}.')

    del driving_distances['driving_distance_set_id']

    return driving_distances


def load_locations_only_csv(path: str) -> pd.DataFrame:
    '''
    Load locations only from a CSV file.
    '''
    if not os.path.isfile(path):
        raise ValueError(f'Polling locations file {path} does not exist.')

    dtype_spec = {'Location': 'str', 'Address': 'str', 'Location type': 'str'}

    return pd.read_csv(path, index_col=False, dtype=dtype_spec)

def load_locations_csv(path: str) -> pd.DataFrame:
    '''
    Load locations from a CSV file.
    '''
    if not os.path.isfile(path):
        raise ValueError(f'Polling locations file {path} does not exist.')

    dtype_spec = {'id_orig': 'str', 'id_dest': 'str'}

    return pd.read_csv(path, index_col=0, dtype=dtype_spec)


def load_driving_distances_csv(path: str) -> pd.DataFrame:
    '''
    Load the driving distances from a CSV file.
    '''
    if not os.path.isfile(path):
        raise ValueError(f'Driving distances file {path} does not exist.')

    dtype_spec = {'id_orig': 'str', 'id_dest': 'str', 'distance_m': np.float64}

    return pd.read_csv(path, index_col=False, dtype=dtype_spec)


@dataclass
class PollingLocationResults:
    polling_locations: pd.DataFrame
    polling_locations_set_id: str = None

def get_polling_locations(
    location_source: Literal['db', 'csv'],
    census_year: str,
    location: str,
    log_distance: bool,
    driving: bool,
) -> PollingLocationResults:
    '''
    Loads the polling locations data either from local files or from the database based on config settings.
    '''

    if not census_year:
        raise ValueError('Invalid Census year for location {location}')

    if location_source == LOCATION_SOURCE_DB:
        print(f'Loading polling locations for {location} from database')

        # Load locations from the database
        polling_locations_set = query.get_location_set(census_year, location, log_distance, driving)
        if not polling_locations_set:
            raise ValueError(f'Could not find location set for census_year: {census_year}, location: {location}, log_distance: {log_distance}, driving: {driving} in the database.')

        df = query.get_locations(
            polling_locations_set_id=polling_locations_set.id,
        )

        # Remove aditional columns that are specific to the database
        del df['polling_locations_set_id']

        return PollingLocationResults(
            polling_locations=df,
            polling_locations_set_id=polling_locations_set.id,
        )

    else:
        file_path = build_locations_distance_file_path(census_year, location, driving, log_distance)
        print(f'Loading polling locations for {location} from {file_path}')

        if not os.path.isfile(file_path):
            raise ValueError(f'Do not currently have any data for {file_path} from location {location}')

        df = load_locations_csv(file_path)

        return PollingLocationResults(
            polling_locations=df,
        )


def clean_dest_type(locations_df: pd.DataFrame, year_list: list[str]):
    '''
    Cleans the destination type column in the DataFrame.
    This function is used to ensure that the destination type is set correctly based on the location type.
    '''
    #select data based on year
    #mark everything but bg_centroid as potential
    #then mark location_types with correct years as
    locations_df['dest_type'].mask(locations_df['dest_type'] != 'bg_centroid', 'potential', inplace = True)

    # Set the dest_type to polling for every row that has a location_type like "2018" or "2020" from the year_list
    locations_df['dest_type'].mask(locations_df['location_type'].str.contains('|'.join(year_list)), 'polling', inplace = True)


#########
#Read the intermediate data frame from file, and pull the relevant rows
#Note this this function is called twice, once for calculating alpha and once for
#the base data set.
#The call for alpha should only take the original polling locations.#########
#########

def clean_data(config: PollingModelConfig, locations_df: pd.DataFrame, for_alpha: bool, log: bool):
    location = config.location
    year_list = config.year

    result_df = locations_df.copy(deep=True)

    #pull out unique location types is this data
    unique_location_types = result_df['location_type'].unique()

    if for_alpha:
        # pylint: disable-next=line-too-long
        bad_location_list = [location_type for location_type in unique_location_types if 'Potential' in location_type or 'centroid' in location_type]
    else:
        bad_location_list = config.bad_types

    polling_location_types = set(result_df[result_df.dest_type == 'polling']['location_type'])

    for year in year_list:
        if not any(str(year) in poll for poll in polling_location_types):
            raise ValueError(f'Do not currently have any data for {location} for {year} from {config.config_file_path}')

    #exclude bad location types
    # The bad types must be valid location types
    if not set(bad_location_list).issubset(set(unique_location_types)):
        # pylint: disable-next=line-too-long
        raise ValueError(f'unrecognized bad location types types {set(bad_location_list).difference(set(unique_location_types))} in {config.config_file_path}' )

    #drop rows of bad location types in df
    result_df = result_df[~result_df['location_type'].isin(bad_location_list)]

    clean_dest_type(result_df, year_list)

    #check that this hasn't created duplicates (should not have); drop these
    result_df = result_df.drop_duplicates()

    #check that population is unique by id_orig
    pop_df = result_df.groupby('id_orig')['population'].agg('unique').str.len()
    if any(pop_df>1):
        raise ValueError(f'Some id_orig has multiple associated populations from {config.config_file_path}')

    # raise error if there are any missing distances
    if len(result_df[pd.isnull(result_df.distance_m)]) > 0:
        # indicate destinations and origins that are missing driving distances
        all_orig = set(result_df.id_orig)
        all_dest = set(result_df.id_dest)
        notna_df = result_df[pd.notna(result_df.distance_m)]
        notna_orig = set(notna_df.id_orig)
        notna_dest = set(notna_df.id_dest)
        missing_origs = all_orig - notna_orig
        missing_dests = all_dest - notna_dest
        if len(missing_dests) > 0:
            print(f'distances missing for {len(missing_dests)} destination(s): {missing_dests}')
        if len(missing_origs) > 0:
            print(f'distances missing for {len(missing_origs)} origin(s): {missing_origs}')
        raise ValueError(f'Some distances are missing for current config setting.')


    #create other useful columns
    result_df['weighted_dist'] = result_df['population'] * result_df['distance_m']

    return result_df

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
