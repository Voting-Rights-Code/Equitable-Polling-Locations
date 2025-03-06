import os
from pathlib import Path
import shutil
import requests
import subprocess
import argparse
import pandas as pd

# TODO fix this
# try:
#     from authentication_files.census_key import census_key
# except:
#     census_key = None

census_key = None

STATE_LOOKUP = {
    'AK': 'Alaska',
    'AL': 'Alabama',
    'AR': 'Arkansas',
    'AS': 'American Samoa',
    'AZ': 'Arizona',
    'CA': 'California',
    'CO': 'Colorado',
    'CT': 'Connecticut',
    'DC': 'District of Columbia',
    'DE': 'Delaware',
    'FL': 'Florida',
    'GA': 'Georgia',
    'GU': 'Guam',
    'HI': 'Hawaii',
    'IA': 'Iowa',
    'ID': 'Idaho',
    'IL': 'Illinois',
    'IN': 'Indiana',
    'KS': 'Kansas',
    'KY': 'Kentucky',
    'LA': 'Louisiana',
    'MA': 'Massachusetts',
    'MD': 'Maryland',
    'ME': 'Maine',
    'MI': 'Michigan',
    'MN': 'Minnesota',
    'MO': 'Missouri',
    'MP': 'Northern Mariana Islands',
    'MS': 'Mississippi',
    'MT': 'Montana',
    'NA': 'National',
    'NC': 'North Carolina',
    'ND': 'North Dakota',
    'NE': 'Nebraska',
    'NH': 'New Hampshire',
    'NJ': 'New Jersey',
    'NM': 'New Mexico',
    'NV': 'Nevada',
    'NY': 'New York',
    'OH': 'Ohio',
    'OK': 'Oklahoma',
    'OR': 'Oregon',
    'PA': 'Pennsylvania',
    'PR': 'Puerto Rico',
    'RI': 'Rhode Island',
    'SC': 'South Carolina',
    'SD': 'South Dakota',
    'TN': 'Tennessee',
    'TX': 'Texas',
    'UT': 'Utah',
    'VA': 'Virginia',
    'VI': 'Virgin Islands',
    'VT': 'Vermont',
    'WA': 'Washington',
    'WI': 'Wisconsin',
    'WV': 'West Virginia',
    'WY': 'Wyoming'
}

def get_all_states_fips_codes(api_key):
    """
    Get the fips codes for all 50 states
    """
    state_keys = requests.get(
        f"https://api.census.gov/data/2020/dec/pl?get=NAME&for=state:*&key={api_key}"
    )
    state_to_fips = pd.Series(dict(state_keys.json()[1:]))
    return state_to_fips

def get_all_state_county_codes(state_fips, api_key):
    """
    Get all county codes for a given state
    """
    r = requests.get(
        f"https://api.census.gov/data/2020/dec/pl?get=NAME&for=county:*&in=state:{state_fips}&key={api_key}"
    )
    county_codes = pd.DataFrame(r.json())
    headers = county_codes.iloc[0].values
    county_codes.columns = headers
    county_codes.drop(index=0, axis=0, inplace=True)
    county_codes['county_name'] = county_codes['NAME'].apply(lambda x: x.split(',')[0])
    return county_codes


def get_county_code(county, all_county_codes):
    """
    Get the county code for a given county
    """
    county_code = all_county_codes.loc[all_county_codes.county_name == county]['county'].values[0]
    return county_code


def pull_metadata(url):
    """
    Helper function for pulling census metadata labels
    """
    labels = requests.get(
        url
    )
    v = labels.json()['variables']
    v = {i: v[i]['label'] for i in v.keys()}
    metadata = pd.DataFrame(pd.Series(v, name='Label'))
    metadata.index.name = "Column Name"
    return metadata


def pull_ptable_data(geography, pnum, state_fips, county_code, api_key):
    """
    Pull P3 and P4 table data and column metadata
    """
    if geography == 'block':
        geo = 'block'
    elif geography == 'block group':
        geo="block%20group"
    r = requests.get(
        f"https://api.census.gov/data/2020/dec/pl?get=group({pnum})&for={geo}:*&in=state:{state_fips}&in=county:{county_code}&in=tract:*&key={api_key}"
    )
    data = pd.DataFrame(r.json())
    metadata = pull_metadata(f"https://api.census.gov/data/2020/dec/pl/groups/{pnum}")

    #reformat data to match manual download (for backwards compatibility)
    headers = data.iloc[0].values
    data.columns = headers
    data = data.drop(['state','county','tract',geography], axis=1)
    data = data[data.columns[~data.columns.str.endswith('NA')]]
    metadata_as_dict = metadata['Label'].to_dict()
    row_0 = [old_name for old_name in data.iloc[0, :]]
    replacement = [metadata_as_dict[old_name] for old_name in row_0]
    data.loc[0] = replacement

    return data, metadata


def save_pdata(df, county_ST, geo, pnum, meta=False, base_path = "./datasets/census/redistricting/"):
    """
    Save off the census redistricting table data and metadata
    """
    fname = Path(base_path).joinpath(f"{county_ST}/")
    if geo=="block":
        fname = fname
    elif geo=="block group":
        fname = fname.joinpath("block group demographics")

    if not os.path.exists(fname):
        os.makedirs(fname)

    if meta==False:
        fname = fname.joinpath(f"DECENNIALPL2020.{pnum}-Data.csv")
    elif meta==True:
        fname = fname.joinpath(f"DECENNIALPL2020.{pnum}-Column-Metadata.csv")

    df.to_csv(fname, index = False)
    return fname


def download_file(url, local_dir):
    """
    Helper function to download shape file from URL to a local directory
    """
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)
    local_filename = Path(local_dir).joinpath(url.split('/')[-1])
    with requests.get(url, stream=True) as r:
        with open(local_filename, 'wb') as f:
            shutil.copyfileobj(r.raw, f)
    print(local_filename)
    return local_filename


def unzip_file(fpath, outdir):
    """
    Unzip archive associated with shape files
    """
    subprocess.run(
        ["tar", "-xf", str(fpath), "-C", str(outdir)]
    )


def pull_tiger_file(state, fips, county_ST, county_code, geo):
    """
    Pull and save tiger shapefile
    """
    if geo == 'block':
        geo = "tabblock20"
    elif geo == 'block group':
        geo = "bg20"
    base_url = f"https://www2.census.gov/geo/tiger/TIGER2020PL/STATE/{fips}_{state.upper()}/{fips}{county_code}/tl_2020_{fips}{county_code}_{geo}.zip"
    output_directory = Path(f"./datasets/census/tiger/{county_ST}/")
    fname = download_file(base_url, output_directory)
    unzip_file(fname, output_directory)
    return base_url, output_directory


def pull_census_data(statecode, county, apikey = census_key, state_lookup=STATE_LOOKUP):
    """
    Given a statecode (i.e. MD or NY),
    and county (full name, must be capitalized properly),
    pull P3 and P4 data and tiger files

    """
    if apikey is None:
        raise ValueError('No census key available. Please request one from the census to download census data. See README.')
    state = state_lookup.get(statecode)
    states_fips = get_all_states_fips_codes(apikey)  # get all fips codes for all states
    fipscode = states_fips[state]

    counties_codes = get_all_state_county_codes(fipscode, apikey)  # get all county codes
    countycode = get_county_code(county, counties_codes)

    # pull and save block-level data and block group data
    for geo in ('block', 'block group'):

        # pull P3 and P4 census tables
        for pnum in ('P3', 'P4'):
            print(f"Now pulling {pnum} data for {geo} geography")
            # pull data
            data, metadata = pull_ptable_data(geo, pnum, fipscode, countycode, apikey)
            # save off dataframe and metadata
            county_ST = county.replace(' ','_')+ '_' + statecode
            save_pdata(data, county_ST, geo, pnum)
            save_pdata(metadata, county_ST, geo, pnum, meta=True)

        # pull tiger files
        print(f"Now pulling tiger data for {geo} geography")
        url, out = pull_tiger_file(state, fipscode, county_ST, countycode, geo)

    return "Success"


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'state', help="U.S. state of interest. Full name, with proper capitalization",
    )
    parser.add_argument(
        'county', help="County of interest. Full name, with proper capitalization"
    )
    #parser.add_argument(
    #    'apikey', help="Census API key"
    #)
    args = parser.parse_args()
    print(args)
    #pull_census_data(args.state, args.county, args.apikey)
    pull_census_data(args.state, args.county)
