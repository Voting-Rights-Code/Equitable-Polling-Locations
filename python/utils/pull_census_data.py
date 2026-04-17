'''Download census redistricting data (P3/P4 tables) and TIGER shapefiles for a given county.

Produces on-disk output in the locations the solver reads from:
- CSVs at `datasets/census/redistricting/<Loc>_<ST>/` (and `.../block group demographics/`).
- TIGER shapefiles at `datasets/census/tiger/<Loc>_<ST>/`.

Authentication resolves in this order: explicit `apikey` arg, `CENSUS_API_KEY` env var,
then `authentication_files/credentials.json`.
'''

import json
import os
from pathlib import Path
import shutil
import zipfile

import pandas as pd
import requests

from python.utils import build_decennial_dir_path, build_decennial_file_paths
from python.utils.utils import build_tiger_location_dir
from python.utils.directory_constants import (
    TABBLOCK_FILE_SUFFIX, BLOCK_GROUP_FILE_SUFFIX,
    BLOCK_GEO, BLOCK_GROUP_GEO, P3_NAME, P4_NAME,
)

HTTP_TIMEOUT_SECONDS = 60


CREDENTIALS_PATH = Path(__file__).resolve().parent.parent.parent / 'authentication_files' / 'credentials.json'


def _load_census_key(credentials_path=CREDENTIALS_PATH):
    '''Load the census API key from the CENSUS_API_KEY env var or credentials JSON file.

    The `CENSUS_API_KEY` environment variable takes precedence when set to a
    non-empty value, which allows the key to be supplied without writing
    `credentials.json` (useful inside containers and CI).

    Args:
        credentials_path: Path to the credentials JSON file.
            Defaults to authentication_files/credentials.json at the project root.

    Returns:
        The census API key string, or None if the env var is unset/empty and
        the file is missing, malformed, or does not contain a 'census_key' field.
    '''
    env_key = os.environ.get('CENSUS_API_KEY')
    if env_key:
        return env_key
    try:
        with open(credentials_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return data.get('census_key')
    except (FileNotFoundError, json.JSONDecodeError):
        return None


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

def get_all_states_fips_codes(census_year, api_key):
    '''Get FIPS codes for all US states from the census API.

    Args:
        census_year: Decennial census year (e.g. 2020).
        api_key: Census API key.

    Returns:
        Pandas Series indexed by full state name with FIPS code values.

    Raises:
        requests.HTTPError: If the census API returns an error status.
    '''
    url = (
        f'https://api.census.gov/data/{census_year}/dec/pl'
        f'?get=NAME&for=state:*&key={api_key}'
    )
    response = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    state_to_fips = pd.Series(dict(response.json()[1:]))
    return state_to_fips


def get_all_state_county_codes(state_fips, census_year, api_key):
    '''Get county codes for every county in a state.

    Args:
        state_fips: Two-digit state FIPS code.
        census_year: Decennial census year (e.g. 2020).
        api_key: Census API key.

    Returns:
        DataFrame with columns including `county_name` and `county` (county code).

    Raises:
        requests.HTTPError: If the census API returns an error status.
    '''
    url = (
        f'https://api.census.gov/data/{census_year}/dec/pl'
        f'?get=NAME&for=county:*&in=state:{state_fips}&key={api_key}'
    )
    response = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    county_codes = pd.DataFrame(response.json())
    headers = county_codes.iloc[0].values
    county_codes.columns = headers
    county_codes.drop(index=0, axis=0, inplace=True)
    county_codes['county_name'] = county_codes['NAME'].apply(lambda x: x.split(',')[0])
    return county_codes


def get_county_code(county, all_county_codes):
    '''Get the county code for a given county from the county-codes DataFrame.

    Args:
        county: Full county name as returned by the census API (e.g. `Tarrant County`).
        all_county_codes: DataFrame from `get_all_state_county_codes`.

    Returns:
        County code string.

    Raises:
        IndexError: If the county is not present in the DataFrame.
    '''
    county_code = all_county_codes.loc[all_county_codes.county_name == county]['county'].values[0]
    return county_code


def pull_metadata(url):
    '''Fetch census column labels from a census metadata endpoint.

    Args:
        url: Census variables URL (e.g. `.../groups/P3`).

    Returns:
        DataFrame indexed by column code with a single `Label` column.

    Raises:
        requests.HTTPError: If the census API returns an error status.
    '''
    response = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    variables = response.json()['variables']
    labels = {code: spec['label'] for code, spec in variables.items()}
    metadata = pd.DataFrame(pd.Series(labels, name='Label'))
    metadata.index.name = 'Column Name'
    return metadata


def pull_ptable_data(geography, pnum, state_fips, county_code, census_year, api_key):
    '''Pull a P3 or P4 table and its column metadata for a given geography.

    Args:
        geography: `BLOCK_GEO` or `BLOCK_GROUP_GEO`.
        pnum: `P3_NAME` or `P4_NAME`.
        state_fips: State FIPS code.
        county_code: County code.
        census_year: Decennial census year.
        api_key: Census API key.

    Returns:
        A `(data, metadata)` tuple of DataFrames.

    Raises:
        ValueError: If `geography` is not a recognised geography.
        requests.HTTPError: If the census API returns an error status.
    '''
    if geography == BLOCK_GEO:
        geo = BLOCK_GEO
    elif geography == BLOCK_GROUP_GEO:
        geo = 'block%20group'
    else:
        raise ValueError(f'unknown geography: {geography}')

    url = (
        f'https://api.census.gov/data/{census_year}/dec/pl'
        f'?get=group({pnum})&for={geo}:*'
        f'&in=state:{state_fips}&in=county:{county_code}&in=tract:*&key={api_key}'
    )
    response = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
    response.raise_for_status()
    data = pd.DataFrame(response.json())
    metadata = pull_metadata(f'https://api.census.gov/data/{census_year}/dec/pl/groups/{pnum}')

    # Reformat data to match manual download (for backwards compatibility).
    headers = data.iloc[0].values
    data.columns = headers
    data = data.drop(['state', 'county', 'tract', geography], axis=1)
    data = data[data.columns[~data.columns.str.endswith('NA')]]
    metadata_as_dict = metadata['Label'].to_dict()
    row_0 = list(data.iloc[0, :])
    replacement = [metadata_as_dict[old_name] for old_name in row_0]
    data.loc[0] = replacement

    return data, metadata


def save_pdata(df, census_year, county_st, geo, pnum, meta=False):
    '''Write a census P-table (data or metadata) to its canonical CSV location.

    Args:
        df: DataFrame to save.
        census_year: Decennial census year.
        county_st: Location identifier, e.g. `Tarrant_County_TX`.
        geo: `BLOCK_GEO` or `BLOCK_GROUP_GEO`.
        pnum: `P3_NAME` or `P4_NAME`.
        meta: If True, save as the column-metadata CSV rather than the data CSV.

    Returns:
        The path to the written CSV.
    '''
    dirname = build_decennial_dir_path(county_st, geo)
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    fname = build_decennial_file_paths(census_year, geo, pnum, county_st, meta)
    df.to_csv(fname, index=False)
    return fname


def download_file(url, local_dir):
    '''Download a file from `url` into `local_dir`, streaming the body.

    Args:
        url: Fully-qualified URL to download.
        local_dir: Destination directory; created if it does not exist.

    Returns:
        Path to the downloaded file on disk.

    Raises:
        requests.HTTPError: If the server returns an error status.
    '''
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)
    local_filename = Path(local_dir).joinpath(url.split('/')[-1])
    with requests.get(url, stream=True, timeout=HTTP_TIMEOUT_SECONDS) as response:
        response.raise_for_status()
        with open(local_filename, 'wb') as out_file:
            shutil.copyfileobj(response.raw, out_file)
    return local_filename


def unzip_file(fpath, outdir):
    '''Extract a `.zip` archive into `outdir`, then delete the archive.

    Args:
        fpath: Path to the `.zip` file.
        outdir: Destination directory (must exist).

    Raises:
        zipfile.BadZipFile: If `fpath` is not a valid zip archive.
    '''
    with zipfile.ZipFile(fpath) as archive:
        archive.extractall(outdir)
    os.remove(fpath)


def pull_tiger_file(state, fips, county_st, county_code, geo, census_year, verbose=False):
    '''Download and extract the TIGER shapefile for a county at the given geography.

    Args:
        state: Full state name (e.g. `Texas`). Used in the TIGER URL path.
        fips: State FIPS code.
        county_st: Location identifier, e.g. `Tarrant_County_TX`.
        county_code: County code.
        geo: `BLOCK_GEO` or `BLOCK_GROUP_GEO`.
        census_year: Decennial census year.
        verbose: If True, print the downloaded archive path. Defaults to False.

    Raises:
        ValueError: If `geo` is not a recognised geography.
        requests.HTTPError: If the TIGER server returns an error status.
        zipfile.BadZipFile: If the downloaded archive is corrupt.
    '''
    if geo == BLOCK_GEO:
        geo_suffix = TABBLOCK_FILE_SUFFIX
    elif geo == BLOCK_GROUP_GEO:
        geo_suffix = BLOCK_GROUP_FILE_SUFFIX
    else:
        raise ValueError(f'unknown geography: {geo}')

    base_url = (
        f'https://www2.census.gov/geo/tiger/TIGER{census_year}PL'
        f'/STATE/{fips}_{state.upper()}/{fips}{county_code}'
        f'/tl_{census_year}_{fips}{county_code}_{geo_suffix}.zip'
    )
    output_directory = Path(build_tiger_location_dir(county_st))
    archive_path = download_file(base_url, output_directory)
    if verbose:
        print(archive_path)
    unzip_file(archive_path, output_directory)


def pull_census_data(statecode, county, census_year, apikey=None, state_lookup=None, verbose=False):
    '''Pull P3 and P4 census data and TIGER shapefiles for a given county.

    Given a state code (e.g. 'MD' or 'NY') and county name (full name,
    properly capitalized), downloads census redistricting data and
    TIGER shapefiles into their canonical on-disk locations.

    Args:
        statecode: Two-letter US state code.
        county: Full county name with proper capitalization.
        census_year: Census year (e.g. 2020) to query data for.
        apikey: Census API key. If None, attempts to load from the
            `CENSUS_API_KEY` env var, then from authentication_files/credentials.json.
        state_lookup: Mapping of state codes to full state names. Defaults to
            the module-level `STATE_LOOKUP`.
        verbose: If True, print per-table and per-file progress messages.
            Defaults to False (silent).

    Returns:
        The string 'Success' on completion.

    Raises:
        ValueError: If no census API key is available.
    '''
    if state_lookup is None:
        state_lookup = STATE_LOOKUP
    if apikey is None:
        apikey = _load_census_key()
    if apikey is None:
        raise ValueError(
            'No census key available. Please request one from the census to download census data. '
            'See README.'
        )

    state = state_lookup.get(statecode)
    states_fips = get_all_states_fips_codes(census_year, apikey)
    fipscode = states_fips[state]

    counties_codes = get_all_state_county_codes(fipscode, census_year, apikey)
    countycode = get_county_code(county, counties_codes)
    county_st = county.replace(' ', '_') + '_' + statecode

    for geo in (BLOCK_GEO, BLOCK_GROUP_GEO):
        for pnum in (P3_NAME, P4_NAME):
            if verbose:
                print(f'Now pulling {pnum} data for {geo} geography')
            data, metadata = pull_ptable_data(geo, pnum, fipscode, countycode, census_year, apikey)
            save_pdata(data, census_year, county_st, geo, pnum)
            save_pdata(metadata, census_year, county_st, geo, pnum, meta=True)

        if verbose:
            print(f'Now pulling tiger data for {geo} geography')
        pull_tiger_file(state, fipscode, county_st, countycode, geo, census_year, verbose=verbose)

    return 'Success'


