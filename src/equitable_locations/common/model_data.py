#######################################
# Created on 6 December 2023
#
# @author: Voting Rights Code
# @attribution: based off of code by Josh Murell
#######################################

import pandas as pd
import math
from equitable_locations.io.model_config import PollingModelConfig


def clean_data(df: pd.DataFrame, config: PollingModelConfig, for_alpha: bool):
    year_list = config.year

    # pull out unique location types is this data
    unique_location_types = df["location_type"].unique()

    if for_alpha:
        bad_location_list = [
            location_type
            for location_type in unique_location_types
            if "Potential" in location_type or "centroid" in location_type
        ]
    else:
        bad_location_list = config.bad_types

    polling_location_types = set(df[df.dest_type == "polling"]["location_type"])
    for year in year_list:
        if not any(str(year) in poll for poll in polling_location_types):
            raise ValueError(f"Do not currently have any data for {config.county_name}, {config.state_name} for {year}")
    # drop duplicates and empty block groups
    df = df.drop_duplicates()  # put in to avoid duplications down the line.
    df = df[df["population"] > 0]

    # exclude bad location types

    # The bad types must be valid location types
    if not set(bad_location_list).issubset(set(unique_location_types)):
        raise ValueError(
            f"unrecognized bad location types types {set(bad_location_list).difference(set(unique_location_types))}"
        )
    # drop rows of bad location types in df
    df = df[~df["location_type"].isin(bad_location_list)]

    # select data based on year
    # select the polling locations only for the indicated years
    # keep all other locations
    not_polling = df[(df.dest_type != "polling")]
    polling_year_list = [df[df.location_type.str.contains(str(year))] for year in year_list]
    polling_year_list.append(not_polling)
    df = pd.concat(polling_year_list)
    # the concatenation will create duplicates if a polling location is used multiple years
    # drop these
    df = df.drop_duplicates()

    # check that population is unique by id_orig
    pop_df = df.groupby("id_orig")["population"].agg("unique").str.len()
    if any(pop_df > 1):
        raise ValueError("Some id_orig has multiple associated populations")

    return df


##########################
# Other functions for data processing
##########################


# determines the maximum of the minimum distances
def get_max_min_dist(dist_df):
    min_dist = dist_df[["id_orig", "distance"]].groupby("id_orig").agg("min")
    max_min_dist = min_dist.distance.max()
    max_min_dist = math.ceil(max_min_dist)
    return max_min_dist


# various alpha function. Really only use alpha_min
def alpha_all(df):
    # add a distance square column
    df["distance_squared"] = df["distance"] * df["distance"]

    # population weighted distances
    distance_sum = sum(df["population"] * df["distance"])
    # population weighted distance squared
    distance_sq_sum = sum(df["population"] * df["distance_squared"])
    alpha = distance_sum / distance_sq_sum
    return alpha


def alpha_min(df):
    # Find the minimal distance to polling location
    min_df = df[["id_orig", "distance", "population"]].groupby("id_orig").agg("min")

    # find the square of the min distances
    min_df["distance_squared"] = min_df["distance"] * min_df["distance"]
    # population weighted distances
    distance_sum = sum(min_df["population"] * min_df["distance"])
    # population weighted distance squared
    distance_sq_sum = sum(min_df["population"] * min_df["distance_squared"])
    alpha = distance_sum / distance_sq_sum
    return alpha


def alpha_mean(df):
    # Find the mean distance to polling location
    mean_df = df[["id_orig", "distance", "population"]].groupby("id_orig").agg("mean")

    # find the square of the min distances
    mean_df["distance_squared"] = mean_df["distance"] * mean_df["distance"]
    # population weighted distances
    distance_sum = sum(mean_df["population"] * mean_df["distance"])
    # population weighted distance squared
    distance_sq_sum = sum(mean_df["population"] * mean_df["distance_squared"])
    alpha = distance_sum / distance_sq_sum
    return alpha
