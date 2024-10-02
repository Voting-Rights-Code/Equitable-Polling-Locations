"""
take csv file as argument
ensure csv has dest_lat, dest_lon, orig_lat, orig_lon
from csv, get dest_lat, dest_lon, orig_lat, orig_lon
call Distance Matrix API to get driving distances IN METERS
    elements = origins * destinations
    must call a compliant number of times
    consider what happens if API returns a non-distance
add GMAP_distance_m to the same csv

make sure there are 2000 rows, GMAP_distance_m matches the row
"""
# import numpy as np
import pandas as pd
from dotenv import load_dotenv
# import requests
import os


def helper(dest_lat, dest_lon, orig_lat, orig_lon):
    # distance_matrix = requests.get(
    #    f"https://maps.googleapis.com/maps/api/distancematrix/json?destinations={
    #        dest_lat}%2C{dest_lon}&origins={orig_lat}%2C{orig_lon}&key={api_key}"
    # ).json()

    # call the google maps with the origin and destination information
    # the  distance information is contained in the elements structure and needs to be normalized into a flat structure
    distance_matrix = pd.read_json(f"https://maps.googleapis.com/maps/api/distancematrix/json?units=metric&destinations={
        dest_lat}%2C{dest_lon}&origins={orig_lat}%2C{orig_lon}&mode=driving&key={api_key}", orient='columns')
    df = pd.json_normalize(distance_matrix['rows'], 'elements')

    # merge the normalized structure back the returned data
    df = distance_matrix.merge(df)
    # return the required data as a pandas series
    return df[['status', 'distance.value', 'origin_addresses', 'destination_addresses']].squeeze()

    # if df.iloc[0]["status"] == "OK":
    #    # already in meters
    #    return df
    # else:
    #    return df["status"], None, None


def add_GMAP_distance_m(file_name: str, api_key: str) -> None:
    df = pd.read_csv(file_name)

    dest_lat, dest_lon, orig_lat, orig_lon = "dest_lat", "dest_lon", "orig_lat", "orig_lon"
    if not {dest_lat, dest_lon, orig_lat, orig_lon}.issubset(df.columns):
        print("not a column")
        return
    """def check_dtype(column: str) -> bool:
        return isinstance(df[column].dtype, np.float64)
    if not (check_dtype(dest_lat) and check_dtype(dest_lon) and check_dtype(orig_lat) and check_dtype(orig_lon)):
        print("column dtype wrong")
        return"""

    # call the api with only the required columns
    df_gmap = df[["dest_lat", "dest_lon", "orig_lat", "orig_lon"]].apply(
        lambda x: helper(*x), axis=1)

    # reindex to break the multi index that is returned
    df_gmap.reset_index(drop=True, inplace=True)

    # set identifiable variable names, combine with original data and save to disk
    df_gmap.rename(columns={'status': 'GMAP_status', 'distance.value': 'GMAP_distance_m1',
                            'origin_addresses': 'GMAP_orig', 'destination_addresses': 'GMAP_dest'}, inplace=True)
    df_gmap = pd.merge(df, df_gmap, how='left',
                       left_index=True, right_index=True)
    # df_gmap.to_csv(file_name, index=False)

    # df["GMAP_distance_m", "GMAP_orig_address", "GMAP_dest_address"] = df[["dest_lat", "dest_lon",
    #                                                                      "orig_lat", "orig_lon"]].apply(lambda x: helper(*x), axis=1)


if __name__ == '__main__':
    file_name = "./datasets/driving/Virginia_Beach_City_VA/Virginia_Beach_City_VA_compare_driving_distances.csv"
    load_dotenv('authentication_files')
    api_key = os.getenv('GMAP_API_KEY')
    # api_key = "AIzaSyB9_7qnQ7himyMWksZ5IjGYkTNQlxQXbUc"  #deactivated.
    add_GMAP_distance_m(file_name, api_key)
