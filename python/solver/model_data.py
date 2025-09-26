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

# pylint: disable-next=wildcard-import,unused-wildcard-import
from .constants import *

#define columns for each input data set
LOCATIONS_COLS = [
    LOC_LOCATION,
    LOC_ADDRESS,
    LOC_LOCATION_TYPE,
    LOC_LAT_LON,
]

# Prefix to add to Shape files to join with demographic data.
GEO_ID_PREFIX = '1000000US'

P3_COLUMNS = [
    CEN_GEO_ID,
    CEN_NAME,
    CEN_P3_001N, # Total population
    CEN_P3_003N, # White alone
    CEN_P3_004N, # Black or African American alone
    CEN_P3_005N, # American Indian or Alaska Native alone
    CEN_P3_006N, # Asian alone
    CEN_P3_007N, # Native Hawaiian and Other Pacific Islander alone
    CEN_P3_008N, # Some other race alone
    CEN_P3_009N, # Two or More Races
]

P4_COLUMNS = [
    CEN_GEO_ID,
    CEN_NAME,
    CEN_P4_001N, # Total population
    CEN_P4_002N, # Total hispanic
    CEN_P4_003N, # Total non_hispanic
]

BLOCK_SHAPE_COLS = [
    BLK_GEOID20,
    BLK_INTPTLAT20,
    BLK_INTPTLON20,
]

BLOCK_GROUP_SHAPE_COLS = [
    BLK_GEOID20,
    BLK_INTPTLAT20,
    BLK_INTPTLON20,
]

FULL_DF_COLS = [
    ID_ORIG,
    ID_DEST,
    SRC_ADDRESS,
    SRC_DEST_LAT,
    SRC_DEST_LON,
    SRC_ORIG_LAT,
    SRC_ORIG_LON,
    SRC_LOCATION_TYPE,
    DEST_TYPE,
    SRC_POPULATION,
    SRC_HISPANIC,
    SRC_NON_HISPANIC,
    SRC_WHITE,
    SRC_BLACK,
    SRC_NATIVE,
    SRC_ASIAN,
    SRC_PACIFIC_ISLANDER,
    SRC_OTHER,
    SRC_MULTIPLE_RACES,
]

@dataclass
class PollingLocationsOnlyResult:
    locations_only: pd.DataFrame
    polling_locations_only_set_id: str=None
    output_path: str=None


def get_polling_locations_only(
        location_source: Literal['db', 'csv'],
        location: str,
        locations_only_path_override: str=None,
) -> PollingLocationsOnlyResult:
    location_only_set_id: str = None
    if location_source == LOCATION_SOURCE_DB:
        location_only_set = query.get_location_only_set(location)
        if not location_only_set:
            raise ValueError(f'Could not find location only set for {location} in the database.')

        location_only_set_id = location_only_set.id
        locations_only_df = query.get_locations_only(location_only_set_id)

        # Rename database columns to match csv columns
        locations_only_df = locations_only_df.rename(
            {
                DB_LOCATION: LOC_LOCATION,
                DB_ADDRESS: LOC_ADDRESS,
                DB_LOCATION_TYPE: LOC_LOCATION_TYPE,
                DB_LAT_LON: LOC_LAT_LON,
            },
            axis=1,
        )

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
    locations_only_df[DEST_TYPE] = LOC_DEST_TYPE_POLLING
    locations_only_df[DEST_TYPE].mask(
        locations_only_df[LOC_LOCATION_TYPE].str.contains(LOC_TYPE_POTENTIAL),
        LOC_DEST_TYPE_POTENTIAL,
        inplace=True,
    )

    #2. change the lat, long into two columns
    locations_only_df[[LOC_LATITUDE, LOC_LONGITUDE]] = locations_only_df[
        LOC_LAT_LON
    ].str.split(pat=', ', expand=True).astype(float)

    locations_only_df.drop([LOC_LAT_LON], axis=1, inplace=True)

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
    blockgroup_gdf = blockgroup_gdf.rename(columns = {
        BLK_GEOID20: LOC_LOCATION, BLK_INTPTLAT20: LOC_LATITUDE, BLK_INTPTLON20: LOC_LONGITUDE,
    })
    blockgroup_gdf[LOC_ADDRESS] = None
    blockgroup_gdf[LOC_LOCATION_TYPE] = BLK_BG_CENTROID
    blockgroup_gdf[DEST_TYPE] = BLK_BG_CENTROID

    return blockgroup_gdf


def get_demographics_block(census_year: str, location: str) -> pd.DataFrame:
    ''' Combine the P3 and P4 census data to generate demographic block data for a specific location and
    census year. '''

    demographics_dir = build_demographics_dir_path(location)
    p3_source_file = build_p3_source_file_path(census_year, location)
    p4_source_file = build_p4_source_file_path(census_year, location)

    if not os.path.exists(demographics_dir):
        statecode = location[-2:]
        locality = location[:-3].replace('_', ' ')
        pull_census_data(statecode, locality)

    if os.path.exists(p3_source_file):
        p3_df = pd.read_csv(p3_source_file,
            header=[0, 1], # DHC files have two headers rows when exported to CSV - tell pandas to take top one
            low_memory=False, # files are too big, set this to False to prevent errors
        )
    else:
        # pylint: disable-next=line-too-long
        raise ValueError(f'Census data from table P3 not found. Download using api or manually following download instruction from README. {p3_source_file}')

    if os.path.exists(p4_source_file):
        p4_df = pd.read_csv(p4_source_file,
            header=[0, 1], # DHC files have two headers rows when exported to CSV - tell pandas to take top one
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

    #select columns for each data set
    p3_df.columns=[multicols[0] for multicols in p3_df.columns]
    p3_df = p3_df[P3_COLUMNS]
    p4_df.columns=[multicols[0] for multicols in p4_df.columns]
    p4_df = p4_df[P4_COLUMNS]
    # blockgroup_gdf = blockgroup_gdf[BLOCK_GROUP_SHAPE_COLS]

    #####
    #Make a demographics table
    #####
    #combine P3 and P4 data to make a joint demographics set
    demographics = p4_df.merge(
        p3_df,
        left_on=[CEN_GEO_ID, CEN_NAME],
        right_on=[CEN_GEO_ID, CEN_NAME],
        how=OUTER,
    )

    #Consistency check for the data pull
    demographics[BLK_POP_DIFF] = demographics.P4_001N - demographics.P3_001N
    if demographics.loc[demographics.Pop_diff != 0].shape[0] != 0:
        raise ValueError('Populations different in P3 and P4. Are both pulled from the voting age universe?')

    #Change column names
    demographics.drop([CEN_P4_001N, BLK_POP_DIFF], axis=1, inplace=True)
    demographics = demographics.rename(columns = {
        CEN_P4_002N: SRC_HISPANIC, CEN_P4_003N: SRC_NON_HISPANIC, CEN_P3_001N: SRC_POPULATION,
        CEN_P3_003N: SRC_WHITE, CEN_P3_004N: SRC_BLACK, CEN_P3_005N: SRC_NATIVE, CEN_P3_006N: SRC_ASIAN,
        CEN_P3_007N: SRC_PACIFIC_ISLANDER, CEN_P3_008N: SRC_OTHER, CEN_P3_009N: SRC_MULTIPLE_RACES,
    })

    #drop geo_id_prefix
    demographics[CEN_GEO_ID] = demographics[CEN_GEO_ID].str.replace(GEO_ID_PREFIX, EMPTY_STRING)

    blocks_gdf = get_blocks_gdf(census_year, location)

    #join with block group shape files
    demographics_block = demographics.merge(
        blocks_gdf,
        left_on=CEN_GEO_ID,
        right_on=BLK_GEOID20,
        how=LEFT,
    )

    #make lat/ long floats
    demographics_block.INTPTLAT20 = demographics_block.INTPTLAT20.astype(float)
    demographics_block.INTPTLON20 = demographics_block.INTPTLON20.astype(float)

    #drop duplicates and empty block groups.  Put in to avoid duplications down the line.
    demographics_block = demographics_block.drop_duplicates()
    demographics_block = demographics_block[demographics_block[SRC_POPULATION] > 0]

    return demographics_block


@dataclass
class BuildSourceResult:
    location_source: Literal['db', 'csv']
    census_year: str
    location: str
    driving: bool
    log_distance: bool
    map_source_date: str=None,
    output_path: str=None
    driving_distance_set_id: str=None
    polling_locations_only_set_id: str=None


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
    map_source_date: str=None,
    log: bool = False,
    locations_only_path_override: str=None,
    output_path_override: str=None,
) -> BuildSourceResult:
    locations_only_results = get_polling_locations_only(location_source, location, locations_only_path_override)
    locations_only_df = locations_only_results.locations_only

    if not is_int(census_year):
        raise ValueError(f'Invalid Census year {census_year} for location {location}')

    if not output_path_override:
        output_path = build_locations_distance_file_path(
            census_year, location, driving, log_distance,
        )
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
    all_locations[LOC_LATITUDE] = pd.to_numeric(all_locations[LOC_LATITUDE])
    all_locations[LOC_LONGITUDE] = pd.to_numeric(all_locations[LOC_LONGITUDE])

    if len(all_locations.Location) != len(set(all_locations.Location)):
        raise ValueError('Non-unique names in Location column. This will cause errors later.')

    #####
    # Cross join polling locations and demographics tables
    #####
    demographics_block_df = get_demographics_block(census_year, location)
    full_df = demographics_block_df.merge(all_locations, how=CROSS)

    #####
    #Rename, select columns
    #####

    full_df = full_df.rename(columns = {
        CEN_GEO_ID: ID_ORIG, LOC_ADDRESS: SRC_ADDRESS, LOC_LATITUDE: SRC_DEST_LAT,
        LOC_LONGITUDE: SRC_DEST_LON, BLK_INTPTLAT20: SRC_ORIG_LAT, BLK_INTPTLON20: SRC_ORIG_LON,
        LOC_LOCATION_TYPE: SRC_LOCATION_TYPE, LOC_LOCATION: ID_DEST,
    })
    full_df = full_df[FULL_DF_COLS]

    #####
    # Calculate appropriate distance
    #####

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
        full_df[DISTANCE_M] = full_df.apply(
            lambda row: haversine((row.orig_lat, row.orig_lon), (row.dest_lat, row.dest_lon)),
            axis=1,
        ) * 1000

        full_df[SRC_SOURCE] = SRC_HAVERSINE_DISTANCE

    #if log distance, modify the source and distance columns
    if log_distance:
        full_df[SRC_SOURCE] = SRC_LOG_WITH_SPACE + full_df[SRC_SOURCE]
        #TODO: why are there 0 distances showing up?
        full_df[DISTANCE_M].mask(full_df[DISTANCE_M] == 0.0, 0.001, inplace=True)
        full_df[DISTANCE_M] = np.log(full_df[DISTANCE_M])

    #####
    #reformat and write to file
    #####

    full_df[ID_ORIG] = full_df[ID_ORIG].astype(str)
    full_df[ID_DEST] = full_df[ID_DEST].astype(str)

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

    if {ID_ORIG, ID_DEST, DISTANCE_M} - set(driving_distances_df.columns):
        raise ValueError('Driving Distances must contain id_orig, id_dest, and distance_m columns')

    combined_df = pd.merge(source_df, driving_distances_df, on=[ID_ORIG, ID_DEST], how=LEFT)

    combined_df[SRC_SOURCE] = SRC_DRIVING_DISTANCE
    return combined_df


def get_csv_driving_distances(census_year: str, map_source_date: str, location: str) -> pd.DataFrame:
    driving_distance_file_path = build_driving_distances_file_path(
        census_year, map_source_date, location,
    )

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

    dtype_spec = {LOC_LOCATION: DTYPE_STR, LOC_ADDRESS: DTYPE_STR, LOC_LOCATION_TYPE: DTYPE_STR}

    return pd.read_csv(path, index_col=False, dtype=dtype_spec)

def load_locations_csv(path: str) -> pd.DataFrame:
    '''
    Load locations from a CSV file.
    '''
    if not os.path.isfile(path):
        raise ValueError(f'Polling locations file {path} does not exist.')

    dtype_spec = {ID_ORIG: DTYPE_STR, ID_DEST: DTYPE_STR}

    return pd.read_csv(path, index_col=0, dtype=dtype_spec)


def load_driving_distances_csv(path: str) -> pd.DataFrame:
    '''
    Load the driving distances from a CSV file.
    '''
    if not os.path.isfile(path):
        raise ValueError(f'Driving distances file {path} does not exist.')

    dtype_spec = {ID_ORIG: DTYPE_STR, ID_DEST: DTYPE_STR, DISTANCE_M: np.float64}

    return pd.read_csv(path, index_col=False, dtype=dtype_spec)


@dataclass
class PollingLocationResults:
    polling_locations: pd.DataFrame
    polling_locations_set_id: str=None

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
            # pylint: disable-next=line-too-long
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
        file_path = build_locations_distance_file_path(
            census_year, location, driving, log_distance,
        )
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
    locations_df[DEST_TYPE].mask(
        locations_df[DEST_TYPE] != BLK_BG_CENTROID,
        LOC_DEST_TYPE_POTENTIAL,
        inplace=True,
    )

    # Set the dest_type to polling for every row that has a location_type like "2018" or "2020" from the year_list
    locations_df[DEST_TYPE].mask(
        locations_df[SRC_LOCATION_TYPE].str.contains('|'.join(year_list)),
        LOC_DEST_TYPE_POLLING,
        inplace=True,
    )


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
    unique_location_types = result_df[SRC_LOCATION_TYPE].unique()

    if for_alpha:
        bad_location_list = [
            location_type
            for location_type in unique_location_types
            if LOC_TYPE_POTENTIAL in location_type or LOC_TYPE_CENTROID in location_type
        ]
    else:
        bad_location_list = config.bad_types

    polling_location_types = set(
        result_df[result_df.dest_type == LOC_DEST_TYPE_POLLING][SRC_LOCATION_TYPE]
    )

    for year in year_list:
        if not any(str(year) in poll for poll in polling_location_types):
            raise ValueError(f'Do not currently have any data for {location} for {year} from {config.config_file_path}')

    # exclude bad location types
    # The bad types must be valid location types
    if not set(bad_location_list).issubset(set(unique_location_types)):
        unrecognized = set(bad_location_list).difference(set(unique_location_types))
        raise ValueError(f'unrecognized bad location types {unrecognized} in {config.config_file_path}')

    #drop rows of bad location types in df
    result_df = result_df[~result_df[SRC_LOCATION_TYPE].isin(bad_location_list)]

    clean_dest_type(result_df, year_list)

    # check that this hasn't created duplicates (should not have); drop these
    result_df = result_df.drop_duplicates()

    # check that population is unique by id_orig
    pop_df = result_df.groupby(ID_ORIG)[SRC_POPULATION].agg(UNIQUE).str.len()
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
        raise ValueError('Some distances are missing for current config setting.')


    #create other useful columns
    result_df[SRC_WEIGHTED_DIST] = result_df[SRC_POPULATION] * result_df[DISTANCE_M]

    return result_df


##########################
#Other functions for data processing
##########################

#determines the maximum of the minimum distances
def get_max_min_dist(dist_df: pd.DataFrame):
    min_dist = dist_df[[ID_ORIG, DISTANCE_M]].groupby(ID_ORIG).agg(MIN)
    max_min_dist = min_dist.distance_m.max()
    max_min_dist = math.ceil(max_min_dist)

    return max_min_dist


#various alpha function. Really only use alpha_min
def alpha_all(df: pd.DataFrame):
    #add a distance square column
    df[SRC_DISTANCE_SQUARED] = df[DISTANCE_M] * df[DISTANCE_M]

    #population weighted distances
    distance_sum = sum(df[SRC_POPULATION] * df[DISTANCE_M])

    #population weighted distance squared
    distance_sq_sum = sum(df[SRC_POPULATION] * df[SRC_DISTANCE_SQUARED])

    alpha = distance_sum / distance_sq_sum

    return alpha


def alpha_min(df: pd.DataFrame):
    #Find the minimal distance to polling location
    min_df= df[[ID_ORIG, DISTANCE_M, SRC_POPULATION]].groupby(ID_ORIG).agg(MIN)

    #find the square of the min distances
    min_df[SRC_DISTANCE_SQUARED] = min_df[DISTANCE_M] * min_df[DISTANCE_M]
    #population weighted distances
    distance_sum = sum(min_df[SRC_POPULATION] * min_df[DISTANCE_M])
    #population weighted distance squared
    distance_sq_sum = sum(min_df[SRC_POPULATION] * min_df[SRC_DISTANCE_SQUARED])

    alpha = distance_sum / distance_sq_sum

    return alpha


def alpha_mean(df: pd.DataFrame):
    #Find the mean distance to polling location
    mean_df = df[[ID_ORIG, DISTANCE_M, SRC_POPULATION]].groupby(ID_ORIG).agg(MEAN)

    #find the square of the min distances
    mean_df[SRC_DISTANCE_SQUARED] = mean_df[DISTANCE_M] * mean_df[DISTANCE_M]
    #population weighted distances
    distance_sum = sum(mean_df[SRC_POPULATION] * mean_df[DISTANCE_M])
    #population weighted distance squared
    distance_sq_sum = sum(mean_df[SRC_POPULATION] * mean_df[SRC_DISTANCE_SQUARED])

    alpha = distance_sum / distance_sq_sum

    return alpha
