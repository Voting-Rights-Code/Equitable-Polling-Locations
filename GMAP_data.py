#!/usr/local/bin/python

import pandas as pd
import numpy as np
import sys
import os
import time
import requests
import json
import tkinter as tk
from tkinter import filedialog
from pathlib import Path
from pathlib import Path
from dotenv import load_dotenv
from time import gmtime, strftime

# Total rows in output dataset
SAMPLE_ROWS = 2000

# Google Maps limits 1,000 elements per minute (1 element =  single origin-destination pair)
REQUESTS_MINUTE = 1000

# get the API Key
load_dotenv('authentication_files')
GMAP_api_key = os.getenv('GMAP_Platform_KEY')


def variables_present(required_variables: list, df: pd.DataFrame):
    """check to see if required variable names exist in a dataframe

    Args:
        required_variables (list): a list of the names of the required variables
        df (pd.DataFrame) : Dataframe to check if the variables exist in 
    Raises:
        ValueError: stop processing if at least one of the variables is missing 
    """
    try:
        # Check if all required columns are present in the DataFrame
        missing_columns = [
            col for col in required_variables if col not in df.columns]
        if missing_columns:
            print(f"Missing required columns in sampling: {missing_columns}")
            sys.exit('Exiting program')
    except SystemExit as e:
        # Stop the program from running and raise an error.
        print(f"Program Exit: ")  # {e}")
    return


def number_subset(var, start, end):
    """split a GeoID into area types

    Args:
        var (str): GeoID
        start (int): starting index
        end (int): ending index (-1)
    Returns:
        string(str) subset Geoid unit
    """
    string = var.apply(str).str[start:end]
    return string.astype(str)


def row_identify(df, var_in, q_val, text):
    """identify rows that have not previously been selected and have
    values less than or equal to a specified quantile.

    Args:
        df (pd.DataFrame): dataframe containing all data to sample from 
        var_in (str): name of axis containing the reference values
        q_val (real): quartile level
        text (str):   text recorded in output column ('Sample') indicating value is less than or equal to q_val
    Returns:
       dsn (panda): input dataset with the addition of values in output column
    """

    df.loc[(df["Sample"].str.len() == 0) &
           (df[var_in] <= df[var_in].quantile(q_val)), "Sample"] = text
    return df


def df_sample(df: pd.DataFrame, quartile: float):
    """given a dataframe select a sample based on pre specified demographic conditions 

    Args:
        df (pd.DataFrame): data frame containing the information to construct the sample from 

    Returns:
        pd.DataFrame:  Dataframe containing the selected sample
    """

    # check to see if variables are present
    variables_present(['white', 'income', 'population'], df)

    # identify  blocks that have the lowest quartile of income,white, and population
    # prevent sampling the same cases by creating a hierarchy of race>income>population>other
    df['Sample'] = ''
    df = row_identify(df, "white", quartile, "rac")
    df = row_identify(df, "income", quartile, "inc")
    df = row_identify(df, "population", quartile, "pop")
    df.loc[df["Sample"].str.len() == 0, "Sample"] = 'oth'
    # create an identifier of which block the row was selected from
    df['Sample_Block'] = df['Sample']
   
    dataset_rows = df.shape[0]
    cnt = df["Sample"].value_counts().to_frame().reset_index()
    group_rows = cnt.shape[0]

    # disproportionate sample to create a dataset with 25% from each group
    sample = df.groupby("Sample", group_keys=False).apply(
        lambda x: x.sample(SAMPLE_ROWS // group_rows), include_groups=False
    )

    # summarize the sample and save the results for reporting
    cnt['pct'] = (SAMPLE_ROWS/group_rows)/cnt['count']
    cnt = cnt.sort_values(by=['Sample'])

    sample_summary = pd.DataFrame()
    # first save the total data frame numbers
    sample_summary = pd.concat([sample_summary,
                                pd.DataFrame([{'Rows_total': dataset_rows, 'Rows_grp': SAMPLE_ROWS, 'grp_pct': SAMPLE_ROWS/dataset_rows}], index=['all'])])
    # now save the sampling groups
    for row in cnt.itertuples():
        sample_summary = pd.concat([sample_summary,
                                    pd.DataFrame([{'Rows_total': row.count, 'Rows_grp': SAMPLE_ROWS//group_rows, 'grp_pct': row.pct}], index=[row.Sample])])

    return sample, sample_summary


def distance_api(dest_lat: float, dest_lon: float, orig_lat: float, orig_lon: float):
    """ given a origin longitude and latitude use google maps
        to find the distance to a destination longitude and latitude.

    Args:
        dest_lat (float): destination latitude
        dest_lon (float): destination longitude
        orig_lat (float): origin latitude
        orig_lon (float): origin longitude 

    Returns:
        series: array containing google map results 
    """
    # call the google maps with the origin and destination information
    # the  distance information is returned in the elements structure and needs to be normalized into a flat structure
    
    url = (
        f"https://maps.googleapis.com/maps/api/distancematrix/json?units=metric"
        f"&destinations={dest_lat}%2C{dest_lon}"
        f"&origins={orig_lat}%2C{orig_lon}"     
        f"&mode=driving&key={GMAP_api_key}"
    )

    # Send a GET request to fetch the data
    response = requests.get(url)
    # Check if the request was successful (status code 200)
    if response.status_code == 200:
        try:
            return pd.Series([
                             response.json().get("status"),
                             response.json()['rows'][0]['elements'][0].get('distance', {}).get('value')
                            ])
            #return pd.Series([df[['status']],df[['distance.value']]])
        except Exception as e:
            # Catch any other errors and print them for debugging
            print(strftime("%Y-%m-%d %H:%M:%S", gmtime()), f'Unexpected Google Map Distance call error: {e}')
            sys.exit(1)
    else:
        print(f"{strftime("%Y-%m-%d %H:%M:%S", gmtime())} Google Maps API Error: {response.status_code} - {response.text}")
        print(strftime("%Y-%m-%d %H:%M:%S", gmtime()), 'Execution Stopping.')
        sys.exit(1)
            
def add_GMAP_distance_m(df: pd.DataFrame, api_key: str):
    """ prepare the data for the API call and combine the distance results with
        the original data. 

    Args:
        df (pd.DataFrame): dataframe containing the destination and origin latitude and longitude 
        api_key (str): API key to use google maps

    Returns:
        pd.DataFrame: dataframe containing the results of the maps API call
    """

    required_variables = ["dest_lat", "dest_lon", "orig_lat", "orig_lon"]
    
    # check to see if variables are present
    variables_present(required_variables, df)

    # Process the records in batches of REQUESTS_MINUTE and 
    # insert a +1 minute pause to comply with Google Maps Usage limits 
    df_gmap = pd.DataFrame()
 
    for i in range (0, len(df), REQUESTS_MINUTE):
        chunk = df.iloc[i:i+REQUESTS_MINUTE].copy()
        print(strftime("%Y-%m-%d %H:%M:%S", gmtime()), 'Batch sent to GMAP API')
        chunk[['GMAP_Status','GMAP_distance_m']] = chunk[required_variables].apply(
               lambda x: distance_api(*x), axis=1,result_type='expand')
        df_gmap = pd.concat([df_gmap,chunk],ignore_index=True)
        if i + REQUESTS_MINUTE < len(df):  # Only wait if there are more records to process
            print(strftime("%Y-%m-%d %H:%M:%S", gmtime()), 'Waiting 1 minute before sending next batch to GMAP API')
            time.sleep(65)  # Delay for 65 seconds

    # to comply with Google Maps Platform Terms Of Service only the difference between the OSM and Google Maps distances can be saved
    df_gmap['Programs_difference_m'] = df_gmap['OSM_distance_m'] - df_gmap['GMAP_distance_m']
    df_gmap.drop(['GMAP_distance_m'],axis=1,inplace=True)
    return (df_gmap)

def main():
        # check if current default directory is the polling location repo
        # by looking for critical dataset directories.   If files not found have user specify repo location
        try:
            path = Path(os.getcwd())
            if (os.path.isdir(path.joinpath('datasets/census')) & os.path.isdir(path.joinpath('datasets/polling'))):
                # path+'/datasets/census') & os.path.isdir(path+'/datasets/polling')):
                OUTPUT_DIRECT = path
            else:
                initial_directory = Path.home()
                OUTPUT_DIRECT = Path(filedialog.askdirectory(
                    initialdir=initial_directory, title="Select Driving Distance Directory"
                ))
        except SystemExit as e:
            print("*Error: Could not read driving distance repo")
            print(f"Program Exit: {e}")

        # Select and read driving distance file
        try:
            dtype = {
                'id_orig': object,
                'id_dest': object,
                'distance_m': float,
                'source': object
            }

            initial_directory = OUTPUT_DIRECT.joinpath('datasets', 'driving')
            file_path = filedialog.askopenfilename(title="Select Driving Distance File", initialdir=initial_directory,
                                                filetypes=[("CSV File", ('*.csv'))])

            print(strftime("%Y-%m-%d %H:%M:%S", gmtime()), 'Reading Driving Direction File')
            Driving_Distance = pd.read_csv(
                file_path, sep=',', engine='pyarrow',  dtype=dtype
            )
            Driving_Distance.sort_values(by=["id_orig", "id_dest"], inplace=True)
            # Create other variables needed to read remaining data files.
            fipscode = str(Driving_Distance['id_orig'].iloc[0])[:2]
            countycode = str(Driving_Distance['id_orig'].iloc[0])[2:5]
            county_ST = os.path.basename(os.path.dirname(file_path))

            Driving_Distance = Driving_Distance.rename(
                columns={'distance_m': 'OSM_distance_m'})
        except SystemExit as e:
            print("*Error: Could not read driving distance file for " + county_ST)
            print(f"Program Exit: {e}")

        # confirm polling location program has been run and an output file exists.  Read in if present
        try:
            # read only these columns:
            cols = ['id_orig', 'id_dest', 'distance_m',
                    'dest_lat', 'dest_lon', 'orig_lat', 'orig_lon', 'location_type',
                    'dest_type', 'population',  'white']
            fn = county_ST + ".csv"
            VB_Data = pd.read_csv(OUTPUT_DIRECT.joinpath("datasets/polling", county_ST, fn),
                                usecols=cols, sep=',', engine='pyarrow')

            VB_Data.sort_values(by=["id_orig", "id_dest"], inplace=True)
            # Data file is at the block level.  Other files at the block group level
            # split Data GEOID into State, County, tract and block group area types for merging
            VB_Data["state"] = number_subset(VB_Data["id_orig"], 0, 2)
            VB_Data["county"] = number_subset(VB_Data["id_orig"], 2, 5)
            VB_Data["tract"] = number_subset(VB_Data["id_orig"], 5, 11)
            VB_Data["block group"] = number_subset(VB_Data["id_orig"], 11, 12)
            print(strftime("%Y-%m-%d %H:%M:%S", gmtime()), 'Reading Polling Location Output File')
        except SystemExit as e:
            print("*Error: Could not read program results file for " + county_ST)
            print(f"Program Exit: {e}")

        # ACS economic data-- read json ACS file from Census Bureau website
        try:
            VB_Income = pd.read_json(
                'https://api.census.gov/data/2020/acs/acs5?get=group(B19013),NAME&for=block%20group:*&in=state:'+fipscode+'%20county:'+countycode)
            # set the first row as the columns names
            VB_Income.columns = VB_Income.iloc[0]
            # drop the first row, reset  index and sort
            VB_Income = VB_Income.drop(0).reset_index(drop=True)
            VB_Income.sort_values(
                by=["state", "county", "tract", "block group"], inplace=True)

            # create meaningful variable name and type
            VB_Income = VB_Income.rename(columns={"B19013_001E": "income"})
            # keep only needed variables
            VB_Income = VB_Income[["state", "county",
                                "tract", "block group", "income"]]
            VB_Income['income'] = VB_Income['income'].astype(int)
            # Replace where the median household income cannot be calculated or reported with NaN
            VB_Income["income"] = VB_Income["income"].replace(-666666666, np.nan)
            print(strftime("%Y-%m-%d %H:%M:%S", gmtime()), 'Fetching ACS Json FIle')
        except json.JSONDecodeError as e:
            # Handle issues related to malformed JSON data
            print("*JSON Error " + f"JSONDecodeError: {e}")
            sys.exit()
        except ValueError as e:
            # This might catch unexpected cases where the data is valid JSON but not suitable for a DataFrame
            print(f"*ValueError: {e}")
            sys.exit()
        except SystemExit as e:
            # Handle any other unexpected errors
            print(f"*An unexpected error occurred: {e}")
            # Stop the program from running and raise an error.
            print(f"Program Exit: {e}")

        # Merge all data together
        # Use the Map daa as the core dataset since all comparisons are made to it
        VB_All = pd.merge(Driving_Distance, VB_Data,
                        on=["id_orig", "id_dest"],
                        how="inner"
                        ).merge(
            VB_Income,
            on=["state", "county", "tract", "block group"],
            how="left"
        )
        print(strftime("%Y-%m-%d %H:%M:%S", gmtime()), 'Merging Files')

        # remove blocks that nobody lives in
        VB_All = VB_All.loc[VB_All["population"] > 0].copy()

        # construct the sample
        VB_sample, sample_summary = df_sample(VB_All, 0.25)
        print(strftime("%Y-%m-%d %H:%M:%S", gmtime()), 'Sampling Done')

        # add the google map distances
        VB_sample = add_GMAP_distance_m(VB_sample, GMAP_api_key)
        print(strftime("%Y-%m-%d %H:%M:%S", gmtime()), 'Google Driving Distances Calculated')

        # write out data files
        fn = county_ST+"_compare_driving_distances.csv"
        fn1 = county_ST+"_sampling_info_driving_distances.csv"
        VB_sample.to_csv(OUTPUT_DIRECT.joinpath("datasets/driving", county_ST, fn))
        sample_summary.to_csv(OUTPUT_DIRECT.joinpath(
            "datasets/driving", county_ST, fn1))
        print(strftime("%Y-%m-%d %H:%M:%S", gmtime()), 'Driving Distance Sample File Written')
        
if __name__ == "__main__":
    main()           