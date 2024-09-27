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
import numpy as np
import pandas as pd
import requests

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
    def helper(row):
        distance_matrix = requests.get(
            f"https://maps.googleapis.com/maps/api/distancematrix/json?destinations={row[dest_lat]}%2C{row[dest_lon]}&origins={row[orig_lat]}%2C{row[orig_lon]}&key={api_key}"
        ).json()
        if distance_matrix["status"] == "OK" and distance_matrix["rows"]:
            return distance_matrix["rows"][0]["elements"][0]["distance"]["value"] # already in meters
        else:
            return distance_matrix["status"]
    df["GMAP_distance_m"] = df.apply(helper, axis=1)
    df.to_csv(file_name, index=False)

if __name__ == '__main__':
    file_name = "./datasets/driving/Virginia_Beach_City_VA/Virginia_Beach_City_VA_compare_driving_distances.csv"
    api_key = "AIzaSyB9_7qnQ7himyMWksZ5IjGYkTNQlxQXbUc"
    add_GMAP_distance_m(file_name, api_key)