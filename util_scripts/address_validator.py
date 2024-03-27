'''
A utility to read in the polling location addresses and their associated lat/lons and compare the to
Google's for the purpose of quality control.

This utility expects the Google Maps API key string to be stored in a single line file called api.key in this directory.
'''

import argparse
from time import sleep
import pandas as pd
import googlemaps
import json
from haversine import haversine, Unit

import address_cvs_headers as headers

API_KEY_FILENAME = 'api.key'

GEO_CODE_PAUSE_TIME = 0.1
''' Time to delay between geocode api calls. '''

VALID_TRESHOLD_METERS = 100
'''
The distance threshold between the original lat/lon and Google's.
If this value is exceeded then the row will be marked with an error in the output file.
'''

# Google maps geocode api query result keys
GOOGLE_MAPS_GEOMETRY = 'geometry'
GOOGLE_MAPS_LOCATION = 'location'
GOOGLE_MAPS_ADDR_FORMATED = 'formatted_address'
GOOGLE_MAPS_LAT = 'lat'
GOOGLE_MAPS_LON = 'lng'

class InvalidGecodeResult(Exception):
    pass

class InvalidFile(Exception):
    pass

def validate_csv(api_key: str, source_file: str, dest_file: str):
    '''
        Perform everything necessary to validate the source file lat lon locations to google's lat/lon and write
        the results out to the dest file.
    '''

    if source_file == dest_file:
        raise InvalidFile('Source and destination files may not be the same.')

    df = pd.read_csv(
        source_file,
        header=0,
        sep=',',
        engine='python',
        skipinitialspace=True,
        quoting=1,
        quotechar='"',
        encoding='utf-8',
    )

    # print(df.head())

    output_results = []

    for _, row in df.iterrows():
        query_address = make_query_address(row)
        row_dict = row.to_dict()

        # Don't query google if we have the lat lon already.
        already_geocoded = row_dict.get(headers.GOOGLE_LAT_COL) and row_dict.get(headers.GOOGLE_LAT_COL)
        if already_geocoded:
            geo_code_result = {}
        else:
            geo_code_result = geo_code(api_key, query_address)

        output_row = { **row_dict, **geo_code_result }

        output_row[headers.QC_DISTANCE] = compute_distance(output_row)
        output_row[headers.WITHIN_THRESHOLD_COL] = is_within_threadhold(output_row)

        print(json.dumps(output_row, indent=4))

        output_results.append(output_row)

        # Avoid hitting the API qurery threshold. Skip this if we didn't need to call out to the api
        if not already_geocoded:
            sleep(GEO_CODE_PAUSE_TIME)

    write_results_file(dest_file, output_results)


def write_results_file(dest_file: str, data: list):
    df = pd.DataFrame(data)

    df.to_csv(dest_file, index=False)


def is_within_threadhold(row: dict) -> bool:
    return row[headers.QC_DISTANCE] <= VALID_TRESHOLD_METERS


def compute_distance(output_row: dict) -> int:
    ''' Compute the distance from the source file's lat and lon to google's geocoded lat and lon '''

    source_point = (output_row[headers.LAT_COL], output_row[headers.LON_COL])
    google_point = (output_row[headers.GOOGLE_LAT_COL], output_row[headers.GOOGLE_LON_COL])

    distance = haversine(source_point, google_point, unit=Unit.METERS)
    return round(distance)


def make_query_address(row) -> str:
    ''' Parse out the address fields from the source csv and create a google api friendly address string '''

    id_col = row[headers.ID_COL]
    address_col = row[headers.ADDRESS_COL]
    city_col = row[headers.CITY_COL]
    state_col = row[headers.STATE_COL]
    zip_col = row[headers.ZIP_COL]
    address = f'{id_col} {address_col}, {city_col}, {state_col} {zip_col}'

    return address


def geo_code(api_key: str, query_address: str) -> dict:
    ''' Call google geocode api and return a dict containing the google official address google's lat/lon '''

    gmaps = googlemaps.Client(key=api_key)
    query_result = gmaps.geocode(query_address)
    if not query_result:
        raise InvalidGecodeResult(f'Invalid geocode result for address: {query_address}')

    return parse_google_geocode(query_result)


def parse_google_geocode(query_result: dict) -> dict:
    ''' Parse the google geocode query and return the values needed using our column headers '''

    geocode = query_result[0]
    google_address = geocode[GOOGLE_MAPS_ADDR_FORMATED]
    geometry = geocode[GOOGLE_MAPS_GEOMETRY]
    location = geometry[GOOGLE_MAPS_LOCATION]
    lat = location[GOOGLE_MAPS_LAT]
    lon = location[GOOGLE_MAPS_LON]
    # print(location)

    return {
        headers.GOOGLE_LAT_COL: lat,
        headers.GOOGLE_LON_COL: lon,
        headers.GOOGLE_ADDR_FORMATED_COL: google_address,
    }


if __name__ == '__main__':
    main_api_key = open(API_KEY_FILENAME, 'r', encoding='UTF8').readline().strip()

    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='A commandline tool to validate addresses against google maps api',
    )
    parser.add_argument('source_file', help='The Source csv file to validate')
    parser.add_argument('dest_file', help='The destination file to write the results to')

    args = parser.parse_args()
    validate_csv(main_api_key, args.source_file, args.dest_file)
