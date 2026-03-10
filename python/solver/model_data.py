'''
Utilities to process the various sources files to run a model against
'''

from dataclasses import dataclass
from typing import Literal

import pandas as pd
import numpy as np
import os
from haversine import haversine
import geopandas as gpd

from python.database.query import Query
from python.utils import (
    build_driving_distances_file_path,
    build_potential_locations_file_path,
    build_distance_file_path,
    build_demographics_dir_path,
    build_p3_source_file_path,
    build_p4_source_file_path,
    is_int,
    get_block_source_file_path,
    get_block_group_block_source_file_path,
    timer,
)

from python.utils.pull_census_data import pull_census_data
from .model_config import PollingModelConfig

# pylint: disable-next=wildcard-import,unused-wildcard-import
from .constants import *

#define columns for each input data set
POTENTIAL_LOCATIONS_COLS = [
    POT_LOC_LOCATION,
    POT_LOC_ADDRESS,
    POT_LOC_LOCATION_TYPE,
    POT_LOC_LAT_LON,
]

P3_COLUMNS = [
    CEN20_GEO_ID,
    CEN20_NAME,
    CEN20_P3_TOTAL_POPULATION, # Total population
    CEN20_P3_WHITE, # White alone
    CEN20_P3_BLACK, # Black or African American alone
    CEN20_P3_NATIVE, # American Indian or Alaska Native alone
    CEN20_P3_ASIAN, # Asian alone
    CEN20_P3_PACIFIC_ISLANDER, # Native Hawaiian and Other Pacific Islander alone
    CEN20_P3_OTHER, # Some other race alone
    CEN20_P3_MULTIPLE_RACES, # Two or More Races
]

P4_COLUMNS = [
    CEN20_GEO_ID,
    CEN20_NAME,
    CEN20_P4_TOTAL_POPULATION, # Total population
    CEN20_P4_HISPANIC, # Total hispanic
    CEN20_NON_HISPANIC, # Total non_hispanic
]

BLOCK_SHAPE_COLS = [
    TIGER20_GEOID20,
    TIGER20_INTPTLAT20,
    TIGER20_INTPTLON20,
]

BLOCK_GROUP_SHAPE_COLS = [
    TIGER20_GEOID20,
    TIGER20_INTPTLAT20,
    TIGER20_INTPTLON20,
]

FULL_DISTANCE_DATA_DF_COLS = [
    DISTANCE_ID_ORIG,
    DISTANCE_ID_DEST,
    DISTANCE_ADDRESS,
    DISTANCE_DEST_LAT,
    DISTANCE_DEST_LON,
    DISTANCE_ORIG_LAT,
    DISTANCE_ORIG_LON,
    DISTANCE_LOCATION_TYPE,
    DISTANCE_DEST_TYPE,
    DISTANCE_TOTAL_POPULATION,
    DISTANCE_HISPANIC,
    DISTANCE_NON_HISPANIC,
    DISTANCE_WHITE,
    DISTANCE_BLACK,
    DISTANCE_NATIVE,
    DISTANCE_ASIAN,
    DISTANCE_PACIFIC_ISLANDER,
    DISTANCE_OTHER,
    DISTANCE_MULTIPLE_RACES,
]

@dataclass
class PotentialLocationsData:
    ''' A simple dataclass to hold potential locations data '''
    potential_locations_df: pd.DataFrame
    potential_locations_set_id: str=None
    output_path: str=None


def get_potential_locations_data(
        data_source: Literal['db', 'csv'],
        location: str,
        potential_locations_path_override: str=None,
        query: Query=None,
) -> PotentialLocationsData:
    '''
    Loads the potential locations source data either from local files or from the database based on
    data_source value.
    '''
    potential_locations_set_id: str = None
    if data_source == DATA_SOURCE_DB:
        potential_locations_set = query.get_potential_locations_set(location)
        if not potential_locations_set:
            raise ValueError(f'Could not find potential location set for {location} in the database.')

        potential_locations_set_id = potential_locations_set.id
        potential_locations_df = query.get_potential_locations(potential_locations_set_id)

        # Rename database columns to match csv columns
        potential_locations_df = potential_locations_df.rename(
            {
                DB_LOCATION: POT_LOC_LOCATION,
                DB_ADDRESS: POT_LOC_ADDRESS,
                DB_LOCATION_TYPE: POT_LOC_LOCATION_TYPE,
                DB_LAT_LON: POT_LOC_LAT_LON,
            },
            axis=1,
        )

        if potential_locations_df.empty:
            raise ValueError(f'No potential locations set {location} id {potential_locations_set.id}.')


    else:
        if potential_locations_path_override:
            # If a path override is provided, use that instead of the default file path
            potential_locations_source_file = potential_locations_path_override
        else:
            potential_locations_source_file = build_potential_locations_file_path(location)

        if os.path.exists(potential_locations_source_file):
            #warnings.warn(f'{file_name} found. Last modified {os.path.getmtime(LOCATION_SOURCE_FILE)}.')
            potential_locations_df = pd.read_csv(potential_locations_source_file)
        else:
            raise ValueError(f'Potential polling location data ({potential_locations_source_file}) not found.')


    potential_locations_df = potential_locations_df[POTENTIAL_LOCATIONS_COLS]

    # The potential locations data needs further processing:
    # 1. add a destination type column
    potential_locations_df[DISTANCE_DEST_TYPE] = DISTANCE_DEST_TYPE_POLLING
    potential_locations_df[DISTANCE_DEST_TYPE].mask(
        potential_locations_df[POT_LOC_LOCATION_TYPE].str.contains(POT_LOC_LOCATION_TYPE_POTENTIAL_SUBSTR),
        DISTANCE_DEST_TYPE_POTENTIAL,
        inplace=True,
    )

    # 2. change the lat, long into two columns
    potential_locations_df[[POT_LOC_LATITUDE, POT_LOC_LONGITUDE]] = potential_locations_df[
        POT_LOC_LAT_LON
    ].str.split(pat=', ', expand=True).astype(float)

    potential_locations_df.drop([POT_LOC_LAT_LON], axis=1, inplace=True)

    return PotentialLocationsData(
        potential_locations_df=potential_locations_df,
        potential_locations_set_id=potential_locations_set_id,
    )


#functions that are steps in build source class

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
        TIGER20_GEOID20: POT_LOC_LOCATION, TIGER20_INTPTLAT20: POT_LOC_LATITUDE,
        TIGER20_INTPTLON20: POT_LOC_LONGITUDE,
    })
    blockgroup_gdf[POT_LOC_ADDRESS] = None
    blockgroup_gdf[POT_LOC_LOCATION_TYPE] = TIGER20_BG_CENTROID
    blockgroup_gdf[DISTANCE_DEST_TYPE] = TIGER20_BG_CENTROID

    return blockgroup_gdf


def get_demographics_block(census_year: str, location: str, census_data_type: str) -> pd.DataFrame:
    '''
    Combine the P3 and P4 census data to generate demographic block data for a specific location and
    census year.
    '''

    demographics_dir = build_demographics_dir_path(census_data_type, location)
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


    #######
    #Clean data
    #######
    #select columns for each data set
    p3_df.columns=[multicols[0] for multicols in p3_df.columns]
    p3_df = p3_df[P3_COLUMNS]
    p4_df.columns=[multicols[0] for multicols in p4_df.columns]
    p4_df = p4_df[P4_COLUMNS]

    #####
    # Make a demographics table
    #####
    # Combine P3 and P4 data to make a joint demographics set
    demographics = p4_df.merge(
        p3_df,
        left_on=[CEN20_GEO_ID, CEN20_NAME],
        right_on=[CEN20_GEO_ID, CEN20_NAME],
        how=PD_OUTER,
    )

    # Consistency check for the data pull
    demographics[TIGER20_POP_DIFF] = demographics[CEN20_P4_TOTAL_POPULATION] - demographics[CEN20_P3_TOTAL_POPULATION]
    if demographics.loc[demographics[TIGER20_POP_DIFF] != 0].shape[0] != 0:
        raise ValueError('Populations different in P3 and P4. Are both pulled from the voting age universe?')

    # Change column names
    demographics.drop([CEN20_P4_TOTAL_POPULATION, TIGER20_POP_DIFF], axis=1, inplace=True)
    demographics = demographics.rename(columns = {
        CEN20_P4_HISPANIC: DISTANCE_HISPANIC, CEN20_NON_HISPANIC: DISTANCE_NON_HISPANIC,
        CEN20_P3_TOTAL_POPULATION: DISTANCE_TOTAL_POPULATION, CEN20_P3_WHITE: DISTANCE_WHITE,
        CEN20_P3_BLACK: DISTANCE_BLACK, CEN20_P3_NATIVE: DISTANCE_NATIVE, CEN20_P3_ASIAN: DISTANCE_ASIAN,
        CEN20_P3_PACIFIC_ISLANDER: DISTANCE_PACIFIC_ISLANDER, CEN20_P3_OTHER: DISTANCE_OTHER,
        CEN20_P3_MULTIPLE_RACES: DISTANCE_MULTIPLE_RACES,
    })

    #drop geo_id_prefix
    demographics[CEN20_GEO_ID] = demographics[CEN20_GEO_ID].str.replace(TIGER20_GEOID_PREFIX, EMPTY_STRING)

    #get block group geographic
    blocks_gdf = get_blocks_gdf(census_year, location)

    #join with block group shape files
    demographics_block = demographics.merge(
        blocks_gdf,
        left_on=CEN20_GEO_ID,
        right_on=TIGER20_GEOID20,
        how=PD_LEFT,
    )

    #make lat/ long floats
    demographics_block[TIGER20_INTPTLAT20] = demographics_block[TIGER20_INTPTLAT20].astype(float)
    demographics_block[TIGER20_INTPTLON20] = demographics_block[TIGER20_INTPTLON20].astype(float)

    #drop duplicates and empty block groups.  Put in to avoid duplications down the line.
    demographics_block = demographics_block.drop_duplicates()
    demographics_block = demographics_block[demographics_block[DISTANCE_TOTAL_POPULATION] > 0]

    return demographics_block


@dataclass
class BuildDistanceMetaData:
    ''' A simple dataclass to hold source meta data information '''
    data_source: Literal['db', 'csv']
    census_year: str
    location: str
    driving: bool
    log_distance: bool
    map_source_date: str=None,
    output_path: str=None
    driving_distance_set_id: str=None
    potential_locations_set_id: str=None


# Old Build source function
@timer
def build_distance_data(
    data_source: Literal['db', 'csv'],
    census_year: str,
    location: str,
    driving: bool,
    log_distance: bool,
    map_source_date: str=None,
    potential_locations_path_override: str=None,
    output_path_override: str=None,
    query: Query=None,
) -> BuildDistanceMetaData:
    '''
    Build distance data set from census data and potential locations data
    and write it to a csv file. An instance of SourceData is returned with metadata about the
    built data set.
    '''

    potential_locations_data = get_potential_locations_data(
        data_source,
        location,
        potential_locations_path_override,
        query=query,
    )
    potential_locations_df = potential_locations_data.potential_locations_df

    if not is_int(census_year):
        raise ValueError(
            f'Invalid Census year {census_year} for location {location}'
        )

    if not output_path_override:
        output_path = build_distance_file_path(
            census_year, location, driving, log_distance,
        )
    else:
        output_path = output_path_override

    # build_distance_meta_data is the return data for this function containing metadata about the built distance data
    build_distance_meta_data = BuildDistanceMetaData(
        data_source=data_source,
        census_year=census_year,
        location=location,
        driving=driving,
        log_distance=log_distance,
        map_source_date=map_source_date,
        potential_locations_set_id=potential_locations_data.potential_locations_set_id,
        output_path=output_path
    )

    #####
    # Make a polling locations table (including block group centroid)
    #####
    blockgroup_gdf = get_blockgroup_gdf(census_year, location)

    # Concatenate
    all_locations = pd.concat([potential_locations_df, blockgroup_gdf])

    # Lat and Long current mix of string and geometry. Make them all floats
    all_locations[POT_LOC_LATITUDE] = pd.to_numeric(all_locations[POT_LOC_LATITUDE])
    all_locations[POT_LOC_LONGITUDE] = pd.to_numeric(all_locations[POT_LOC_LONGITUDE])

    if len(all_locations.Location) != len(set(all_locations.Location)):
        raise ValueError('Non-unique names in Location column. This will cause errors later.')

    #####
    # Cross join polling locations and demographics tables
    #####
    demographics_block_df = get_demographics_block(census_year, location)
    distance_df = demographics_block_df.merge(all_locations, how=PD_CROSS)

    #####
    # Rename, select columns
    #####

    distance_df = distance_df.rename(columns = {
        CEN20_GEO_ID: DISTANCE_ID_ORIG, POT_LOC_ADDRESS: DISTANCE_ADDRESS, POT_LOC_LATITUDE: DISTANCE_DEST_LAT,
        POT_LOC_LONGITUDE: DISTANCE_DEST_LON, TIGER20_INTPTLAT20: DISTANCE_ORIG_LAT,
        TIGER20_INTPTLON20: DISTANCE_ORIG_LON, POT_LOC_LOCATION_TYPE: DISTANCE_LOCATION_TYPE,
        POT_LOC_LOCATION: DISTANCE_ID_DEST,
    })
    distance_df = distance_df[FULL_DISTANCE_DATA_DF_COLS]

    #####
    # Calculate appropriate distance
    #####
    if driving:
        # Load driving distances to insert them into distance_df
        if data_source == DATA_SOURCE_DB:
            # Load the driving_distances_df from DB
            driving_distance_set = query.find_driving_distance_set(census_year, map_source_date, location)
            if not driving_distance_set:
                # pylint: disable-next=line-too-long
                raise ValueError('DrivingDistance set not found in database for census_year {census_year}, map_source_date {map_source_date}, location {location}.',)

            build_distance_meta_data.driving_distance_set_id = driving_distance_set.id
            driving_distances_df = get_db_driving_distances(query, driving_distance_set.id)
        else:
            # Load the driving_distances_df from CSV
            driving_distances_df = get_csv_driving_distances(census_year, map_source_date, location)

        distance_df = insert_driving_distances(distance_df, driving_distances_df)

    else:
        # driving == false so calculate haversine distances instead of using driving distances
        distance_df[DISTANCE_DISTANCE_M] = distance_df.apply(
            lambda row: haversine((row.orig_lat, row.orig_lon), (row.dest_lat, row.dest_lon)),
            axis=1,
        ) * 1000

        distance_df[DISTANCE_SOURCE] = DISTANCE_SOURCE_HAVERSINE_DISTANCE

    # if log distance, modify the source and distance columns
    if log_distance:
        distance_df[DISTANCE_SOURCE] = DISTANCE_SOURCE_LOG_WITH_SPACE + distance_df[DISTANCE_SOURCE]
        #TODO: why are there 0 distances showing up?
        distance_df[DISTANCE_DISTANCE_M].mask(distance_df[DISTANCE_DISTANCE_M] == 0.0, 0.001, inplace=True)
        distance_df[DISTANCE_DISTANCE_M] = np.log(distance_df[DISTANCE_DISTANCE_M])

    # Ensure DISTANCE_ID_ORIG and DISTANCE_ID_DEST are strings
    distance_df[DISTANCE_ID_ORIG] = distance_df[DISTANCE_ID_ORIG].astype(str)
    distance_df[DISTANCE_ID_DEST] = distance_df[DISTANCE_ID_DEST].astype(str)

    #####
    # Reformat and write to file (making directory if it doesn't exist)
    #####

    output_dir = os.path.basename(output_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    distance_df.to_csv(output_path, index = True)

    # Return metadata about the built distance data
    return build_distance_meta_data


def insert_driving_distances(
    distance_df: pd.DataFrame,
    driving_distances_df: pd.DataFrame,
) -> pd.DataFrame:
    '''
    Given a dataframe with origin and destination ids, update the distance_m column
    with driving distances in the given driving distance file. If distance_m exists in df, it
    will be renamed haversine_m.

    Arguments
    distance_df: A pandas DataFrame that contains id_orig and id_dest
    driving_distances_df: driving distance data frame with id_orig, id_dest, and distance_m columns

    Raises
    ValueError - if anything goes wrong (missing file, bad format, missing data)

    Returns
    The original dataframe with the distance_m column populated with the driving distances.
    '''

    if {DISTANCE_ID_ORIG, DISTANCE_ID_DEST, DISTANCE_DISTANCE_M} - set(driving_distances_df.columns):
        raise ValueError('Driving Distances must contain id_orig, id_dest, and distance_m columns')

    combined_df = pd.merge(distance_df, driving_distances_df, on=[DISTANCE_ID_ORIG, DISTANCE_ID_DEST], how=PD_LEFT)

    combined_df[DISTANCE_SOURCE] = DISTANCE_SOURCE_DRIVING_DISTANCE
    return combined_df


def get_csv_driving_distances(census_year: str, map_source_date: str, location: str) -> pd.DataFrame:
    '''
    Builds the path to the driving distances file and uses it to call load_driving_distances_csv to load
    the driving distances from the csv file.
    '''
    driving_distance_file_path = build_driving_distances_file_path(
        census_year, map_source_date, location,
    )

    if not os.path.exists(driving_distance_file_path):
        raise ValueError(f'Driving Distance File ({driving_distance_file_path}) not found.')

    return load_driving_distances_csv(driving_distance_file_path)


def get_db_driving_distances(query: Query, driving_distance_set_id: str) -> pd.DataFrame:
    '''
    Loads the driving distances from the database from the specified driving distance set id
    '''
    driving_distances = query.get_driving_distances(driving_distance_set_id)
    if driving_distances.empty:
        raise ValueError(f'No driving distances for distance set {driving_distance_set_id}.')

    del driving_distances['driving_distance_set_id']

    return driving_distances


def load_potential_locations_csv(potential_locations_csv_path: str) -> pd.DataFrame:
    '''
    Load potential locations from a CSV file.
    '''
    if not os.path.isfile(potential_locations_csv_path):
        raise ValueError(f'Potential locations file {potential_locations_csv_path} does not exist.')

    dtype_spec = {
        POT_LOC_LOCATION: PD_DTYPE_STR,
        POT_LOC_ADDRESS: PD_DTYPE_STR,
        POT_LOC_LOCATION_TYPE: PD_DTYPE_STR,
    }

    return pd.read_csv(potential_locations_csv_path, index_col=False, dtype=dtype_spec)


def load_distance_data_csv(distance_data_csv_path: str) -> pd.DataFrame:
    '''
    Load distance data from a CSV file.
    '''
    if not os.path.isfile(distance_data_csv_path):
        raise ValueError(f'Distance data file {distance_data_csv_path} does not exist.')

    dtype_spec = {DISTANCE_ID_ORIG: PD_DTYPE_STR, DISTANCE_ID_DEST: PD_DTYPE_STR}

    return pd.read_csv(distance_data_csv_path, index_col=0, dtype=dtype_spec)


def load_driving_distances_csv(driving_distance_file_path: str) -> pd.DataFrame:
    '''
    Load the driving distances from a CSV file from disk.
    '''
    if not os.path.isfile(driving_distance_file_path):
        raise ValueError(f'Driving distances file {driving_distance_file_path} does not exist.')

    dtype_spec = {DISTANCE_ID_ORIG: PD_DTYPE_STR, DISTANCE_ID_DEST: PD_DTYPE_STR, DISTANCE_DISTANCE_M: np.float64}

    return pd.read_csv(driving_distance_file_path, index_col=False, dtype=dtype_spec)


@dataclass
class DistanceData:
    ''' A simple dataclass to hold distance data and associated metadata '''
    distance_df: pd.DataFrame
    distance_data_set_id: str = None

def get_distance_data_csv(
    census_year: str,
    location: str,
    log_distance: bool,
    driving: bool,
    log: bool,
) -> DistanceData | None:
    '''
    Builds the file path and loads the distance data from a CSV file using load_distance_data_csv

    Returns
    None if the file does not exist, otherwise returns the DistanceData object
    '''
    distance_data_csv_path = build_distance_file_path(census_year, location, driving, log_distance)

    if not os.path.isfile(distance_data_csv_path):
        return None

    if log:
        print(f'Loading distance data for {location} from {distance_data_csv_path}')

    distance_df = load_distance_data_csv(distance_data_csv_path)

    return DistanceData(
        distance_df=distance_df,
    )


def get_distance_data_db(
        census_year: str,
        location: str,
        log_distance: bool,
        driving: bool,
        query: Query,
        log: bool,
) -> DistanceData:
    ''' Get the distance data from the database '''
    if log:
        print(f'Loading distance data for {location} from database')

    # Load locations from the database
    distance_data_set = query.get_distance_data_set(census_year, location, log_distance, driving)
    if not distance_data_set:
        raise ValueError(
            # pylint: disable-next=line-too-long
            f'Could not find location set for census_year: {census_year}, location: {location}, log_distance: {log_distance}, driving: {driving} in the database. To import the data to the database, run python.scripts.db_import_locations_cli with the desired parameters.',
        )

    df = query.get_distance_data(
        distance_data_set_id=distance_data_set.id,
    )

    # Remove aditional columns that are specific to the database
    del df['distance_data_set_id']

    return DistanceData(
        distance_df=df,
        distance_data_set_id=distance_data_set.id,
    )


@timer
def get_distance_data(
    data_source: Literal['db', 'csv'],
    census_year: str,
    location: str,
    log_distance: bool,
    driving: bool,
    query: Query=None,
    log: bool=False,
) -> DistanceData:
    '''
    Gets the distance data either from local files or from the database based on data_source.
    '''

    if not census_year:
        raise ValueError('Invalid Census year for location {location}')

    # Attempt to get the locations locally first - this saves much time if they have already been saved locally
    distance_data = get_distance_data_csv(
        census_year=census_year, location=location, log_distance=log_distance, driving=driving, log=log,
    )

    if distance_data:
        return distance_data

    if data_source != DATA_SOURCE_DB:
        # If data source is not database, we cannot proceed further
        # pylint: disable-next=line-too-long
        raise ValueError(f'Polling location data cannot be found for census_year={census_year}, log_distance={log_distance}, driving={driving}, location {location}')

    # distance_data was not found locally, we now have to get it from the database
    distance_data = get_distance_data_db(
        census_year=census_year, location=location, log_distance=log_distance, driving=driving, query=query, log=log,
    )

    # Write the locations out locally
    output_path = build_distance_file_path(
        census_year, location, driving, log_distance,
    )

    # The following writes the distance data to a local CSV file as a way to cache it for future use
    output_dir = os.path.dirname(output_path)
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)

    distance_data.distance_df.to_csv(output_path, index=True)

    return distance_data


# Misc helper functions for filtering distance data

def filter_dest_type(distance_df: pd.DataFrame, year_list: list[str]):
    '''
    Cleans the destination type column in the distance_df DataFrame.
    This function is used to ensure that the destination type is set correctly based on the location type.
    '''
    #select data based on year
    #mark everything but bg_centroid as potential
    #then mark location_types with correct years as
    distance_df[DISTANCE_DEST_TYPE].mask(
        distance_df[DISTANCE_DEST_TYPE] != TIGER20_BG_CENTROID,
        DISTANCE_DEST_TYPE_POTENTIAL,
        inplace=True,
    )

    # Set the dest_type to polling for every row that has a location_type like "2018" or "2020" from the year_list
    distance_df[DISTANCE_DEST_TYPE].mask(
        distance_df[DISTANCE_LOCATION_TYPE].str.contains('|'.join(year_list)),
        DISTANCE_DEST_TYPE_POLLING,
        inplace=True,
    )


# pylint: disable-next=unused-argument
def filter_distance_data(config: PollingModelConfig, distance_df: pd.DataFrame, for_alpha: bool, log: bool):
    '''
    Reads the intermediate data frame from file, and pull the relevant rows.
    Notes:
        - This this function is called twice, once for calculating alpha and once for
          the base data set.
        - The call for alpha should only take the original polling locations
    '''
    location = config.location
    year_list = config.year

    filtered_distance_df = distance_df.copy(deep=True)

    # Pull out unique location types is this data
    unique_location_types = filtered_distance_df[DISTANCE_LOCATION_TYPE].unique()

    if for_alpha: #if this is running to calculate alpha, remove all potential locations and centroids.
                    #Note, this keeps all historical locations from all years.
        bad_location_list = [
            location_type
            for location_type in unique_location_types
            if POT_LOC_LOCATION_TYPE_POTENTIAL_SUBSTR in location_type
                or DISTANCE_LOCATION_TYPE_CENTROID_SUBSTR in location_type
        ]
    else:
        bad_location_list = config.bad_types

    polling_location_types = set(
        filtered_distance_df[filtered_distance_df.dest_type == DISTANCE_DEST_TYPE_POLLING][DISTANCE_LOCATION_TYPE]
    )

    for year in year_list:
        if not any(str(year) in poll for poll in polling_location_types):
            raise ValueError(f'Do not currently have any data for {location} for {year} from {config.config_file_path}')

    # Exclude bad location types
    # The bad types must be valid location types
    if not set(bad_location_list).issubset(set(unique_location_types)):
        unrecognized = set(bad_location_list).difference(set(unique_location_types))
        raise ValueError(f'unrecognized bad location types {unrecognized} in {config.config_file_path}')

    # Drop rows of bad location types in df
    filtered_distance_df = filtered_distance_df[~filtered_distance_df[DISTANCE_LOCATION_TYPE].isin(bad_location_list)]

    filter_dest_type(filtered_distance_df, year_list)

    # Check that this hasn't created duplicates (should not have); drop these
    filtered_distance_df = filtered_distance_df.drop_duplicates()

    # Check that population is unique by id_orig
    pop_df = filtered_distance_df.groupby(DISTANCE_ID_ORIG)[DISTANCE_TOTAL_POPULATION].agg(PD_UNIQUE).str.len()
    if any(pop_df>1):
        raise ValueError(f'Some id_orig has multiple associated populations from {config.config_file_path}')

    # Raise error if there are any missing distances
    if len(filtered_distance_df[pd.isnull(filtered_distance_df.distance_m)]) > 0:
        # indicate destinations and origins that are missing driving distances
        all_orig = set(filtered_distance_df.id_orig)
        all_dest = set(filtered_distance_df.id_dest)
        notna_df = filtered_distance_df[pd.notna(filtered_distance_df.distance_m)]
        notna_orig = set(notna_df.id_orig)
        notna_dest = set(notna_df.id_dest)
        missing_origs = all_orig - notna_orig
        missing_dests = all_dest - notna_dest
        if len(missing_dests) > 0:
            print(f'distances missing for {len(missing_dests)} destination(s): {missing_dests}')
        if len(missing_origs) > 0:
            print(f'distances missing for {len(missing_origs)} origin(s): {missing_origs}')
        raise ValueError('Some distances are missing for current config setting.')

    # Create other useful columns
    filtered_distance_df[DISTANCE_WEIGHTED_DIST] = (
        filtered_distance_df[DISTANCE_TOTAL_POPULATION] * filtered_distance_df[DISTANCE_DISTANCE_M]
    )

    return filtered_distance_df


def alpha_min(df: pd.DataFrame) -> float:
    ''' Finds the minimal distance to polling location '''

    min_df = df[
        [DISTANCE_ID_ORIG, DISTANCE_DISTANCE_M, DISTANCE_TOTAL_POPULATION]
    ].groupby(DISTANCE_ID_ORIG).agg(PD_MIN)

    #find the square of the min distances
    min_df[DISTANCE_DISTANCE_SQUARED] = min_df[DISTANCE_DISTANCE_M] * min_df[DISTANCE_DISTANCE_M]

    #population weighted distances
    distance_sum = sum(min_df[DISTANCE_TOTAL_POPULATION] * min_df[DISTANCE_DISTANCE_M])

    #population weighted distance squared
    distance_sq_sum = sum(min_df[DISTANCE_TOTAL_POPULATION] * min_df[DISTANCE_DISTANCE_SQUARED])

    alpha = distance_sum / distance_sq_sum

    return alpha
