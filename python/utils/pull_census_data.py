'''Download census redistricting data (P3/P4 tables), CVAP data, and TIGER shapefiles for a given county.

Produces on-disk output in the locations the solver reads from:
- CSVs at `datasets/census/redistricting/<Loc>_<ST>/` (and `.../block group demographics/`).
- TIGER shapefiles at `datasets/census/tiger/<Loc>_<ST>/`.

Authentication resolves in this order: explicit `apikey` arg, `CENSUS_API_KEY` env var,
then `authentication_files/credentials.json`.
'''

import io
import json
import os
import zipfile
from pathlib import Path
import time
from typing import Any, Callable, Optional

import pandas as pd
import requests

from python.utils import (
    build_redistricting_dir_path, build_redistricting_file_paths,
    build_CVAP_dir_path, build_CVAP_source_file_path,
    build_tiger_location_dir,
    build_RDH_predicted_vap_dir_path,
)
from python.utils.directory_constants import (
    TABBLOCK_FILE_SUFFIX, BLOCK_GROUP_FILE_SUFFIX,
    BLOCK_GEO, BLOCK_GROUP_GEO, P3_NAME, P4_NAME,
)

HTTP_TIMEOUT_SECONDS = 300
HTTP_MAX_RETRIES = 3            # total attempts per request
HTTP_RETRY_BACKOFF_SECONDS = 2  # base for exponential backoff (~2s, then 4s)
DOWNLOAD_CHUNK_SIZE = 1024 * 1024  # 1 MiB streaming chunk

_RETRYABLE_REQUEST_ERRORS = (
    requests.exceptions.ConnectionError,
    requests.exceptions.ChunkedEncodingError,
    requests.exceptions.Timeout,
    requests.exceptions.HTTPError,
)


def _request_with_retries(
    operation: Callable[[], Any],
    description: str,
    sleep: Optional[Callable[[float], None]] = None,
) -> Any:
    '''Run an HTTP operation, retrying transient failures with exponential backoff.

    Args:
        operation: Zero-argument callable that performs the request and returns a result.
        description: Short label for the operation, used in retry notices.
        sleep: Callable used to pause between attempts. Defaults to time.sleep;
            injected in tests so they run instantly.

    Returns:
        The value returned by operation().

    Raises:
        requests.exceptions.HTTPError: A non-5xx (e.g. 4xx) error, raised immediately;
            or the last 5xx error once retries are exhausted.
        requests.exceptions.RequestException: The last transient connection/timeout
            error once retries are exhausted.
    '''
    if sleep is None:
        sleep = time.sleep
    for attempt in range(1, HTTP_MAX_RETRIES + 1):
        try:
            return operation()
        except _RETRYABLE_REQUEST_ERRORS as error:
            non_retryable_status = (
                isinstance(error, requests.exceptions.HTTPError)
                and not _is_retryable_http_error(error)
            )
            if non_retryable_status or attempt == HTTP_MAX_RETRIES:
                raise
            print(
                f'Transient error ({description}): {error}; '
                f'retrying ({attempt + 1}/{HTTP_MAX_RETRIES})...'
            )
            sleep(HTTP_RETRY_BACKOFF_SECONDS * 2 ** (attempt - 1))
    raise AssertionError('retry loop exited without returning or raising')


def _is_retryable_http_error(error: requests.exceptions.HTTPError) -> bool:
    '''Return whether an HTTPError represents a transient (retryable) failure.

    Args:
        error: The HTTPError raised by response.raise_for_status().

    Returns:
        True when the attached response has a 5xx status code (e.g. 520);
        False for 4xx errors or when no response is attached.
    '''
    response = error.response
    return response is not None and 500 <= response.status_code < 600


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

def _load_rdh_credentials(credentials_path=CREDENTIALS_PATH) -> tuple[Optional[str], Optional[str]]:
    """Resolve the RDH username and password from env vars, then the credentials file.

    `RDH_USERNAME` / `RDH_PASSWORD` env vars (forwarded into the container by
    `run.py`) take precedence over the `rdh_username` / `rdh_password` fields in
    `credentials.json`. Each value resolves independently, so a username in the
    environment and a password in the file resolve together.

    Args:
        credentials_path: Path to the credentials JSON file. Defaults to
            authentication_files/credentials.json at the project root.

    Returns:
        A (username, password) tuple; each element is None when that value is
        unset in both the environment and the credentials file.
    """
    username = os.environ.get('RDH_USERNAME')
    password = os.environ.get('RDH_PASSWORD')
    if username and password:
        return username, password
    try:
        with open(credentials_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        data = {}
    return (username or data.get('rdh_username'), password or data.get('rdh_password'))


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

RDH_LIST_URL = 'https://redistrictingdatahub.org/wp-json/download/list'


def get_census_json(url: str) -> Any:
    '''GET a census API URL and return its parsed JSON, retrying transient failures.

    Args:
        url: Fully-qualified census API URL.

    Returns:
        The parsed JSON body (a list or dict, depending on the endpoint).

    Raises:
        requests.exceptions.HTTPError: On a non-retryable status, or once retries
            are exhausted.
    '''
    def operation() -> Any:
        response = requests.get(url, timeout=HTTP_TIMEOUT_SECONDS)
        response.raise_for_status()
        return response.json()
    return _request_with_retries(operation, f'GET {url}')

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
    data = get_census_json(url)
    state_to_fips = pd.Series(dict(data[1:]))
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
    county_codes = pd.DataFrame(get_census_json(url))
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
    variables = get_census_json(url)['variables']
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
    data = pd.DataFrame(get_census_json(url))
    metadata = pull_metadata(f'https://api.census.gov/data/{census_year}/dec/pl/groups/{pnum}?key={api_key}')

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
    dirname = build_redistricting_dir_path(county_st, geo)
    if not os.path.exists(dirname):
        os.makedirs(dirname)

    fname = build_redistricting_file_paths(census_year, geo, pnum, county_st, meta)
    df.to_csv(fname, index=False)
    return fname

def save_CVAP_data(df, census_year, county_ST):
    """
    Save off the CVAP data
    """
    
    dirname = build_CVAP_dir_path(county_ST)

    if not os.path.exists(dirname):
        os.makedirs(dirname)

    fname = build_CVAP_source_file_path(census_year, county_ST)

    df.to_csv(fname, index = False)
    return fname

def download_file(url, local_dir):
    '''Download a file from `url` into `local_dir`, streaming the body.

    Retries transient failures (5xx, dropped or mid-stream-broken connections,
    timeouts) with exponential backoff; the destination is rewritten on each
    attempt so a truncated partial download is overwritten cleanly.

    Args:
        url: Fully-qualified URL to download.
        local_dir: Destination directory; created if it does not exist.

    Returns:
        Path to the downloaded file on disk.

    Raises:
        requests.HTTPError: If the server returns a non-retryable status, or a
            5xx status once retries are exhausted.
    '''
    if not os.path.exists(local_dir):
        os.makedirs(local_dir)
    local_filename = Path(local_dir).joinpath(url.split('/')[-1])

    def operation():
        with requests.get(url, stream=True, timeout=HTTP_TIMEOUT_SECONDS) as response:
            response.raise_for_status()
            with open(local_filename, 'wb') as out_file:
                for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK_SIZE):
                    out_file.write(chunk)
        return local_filename

    return _request_with_retries(operation, f'download {url}')


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

    output_directory = Path(build_tiger_location_dir(county_st))
    expected_shp = output_directory / f'tl_{census_year}_{fips}{county_code}_{geo_suffix}.shp'
    if expected_shp.exists():
        if verbose:
            print(f'Tiger data already exists at {expected_shp}, skipping download.')
        return

    base_url = (
        f'https://www2.census.gov/geo/tiger/TIGER{census_year}PL'
        f'/STATE/{fips}_{state.upper()}/{fips}{county_code}'
        f'/tl_{census_year}_{fips}{county_code}_{geo_suffix}.zip'
    )
    archive_path = download_file(base_url, output_directory)
    if verbose:
        print(archive_path)
    unzip_file(archive_path, output_directory)

def pull_state_CVAP_data(state, username, password, census_year, rdh_url = RDH_LIST_URL):
    """Download the most recent block-level CVAP data for a state from the RDH API.

    Selects the most recent available CVAP dataset whose year falls within the census
    decade [census_year, census_year+10). For example, with census_year='2020', it
    will prefer a 2024 or 2023 release over the original 2020 release.

    Args:
        state: Full state name (e.g. 'Georgia').
        username: RDH API username.
        password: RDH API password.
        census_year: Four-digit decennial census year string (e.g. '2020'). Defines
            the start of the search window; data from the next decade is excluded.

    Returns:
        DataFrame containing block-level CVAP data for the state.

    Raises:
        ValueError: When no dataset is found in the census window, or when multiple
            datasets share the same most-recent year.
    """
    
    #Get the RDH catalog and filter to the block-level CSV for this state and year
    list_params = {
        'username': username,
        'password': password,
        'format': 'csv',
        'states': state,
        'keywords': 'CVAP',
    }
    list_response = requests.get(rdh_url, params=list_params, timeout=60)
    catalog = pd.read_csv(io.StringIO(list_response.content.decode('utf-8')))

    # Find all block-level CSV rows, extract their year, and pick the most recent
    # within the census decade [census_year, census_year+10).
    census_year_int = int(census_year)
    next_census_year = census_year_int + 10

    candidates = catalog[
        catalog['Title'].str.contains('Block Level', case=False, na=False)
        & (catalog['Format'] == 'CSV')
    ].copy()
    candidates['_year'] = candidates['Title'].str.extract(r'\((\d{4})\)')[0].astype(float)
    candidates = candidates[
        (candidates['_year'] >= census_year_int) & (candidates['_year'] < next_census_year)
    ]

    if candidates.shape[0] == 0:
        raise ValueError(
            f'No block-level CVAP CSV found for {state} in census window '
            f'{census_year}-{next_census_year - 1} in the RDH catalog.'
        )

    most_recent_year = candidates['_year'].max()
    matches = candidates[candidates['_year'] == most_recent_year]

    if matches.shape[0] > 1:
        raise ValueError(
            f'Multiple block-level CVAP CSVs found for {state} year {int(most_recent_year)}: '
            f'{list(matches["Title"])}'
        )

    # Download the zip, extract the CSV, and return as a DataFrame
    listing_url = matches.iloc[0]['URL']
    file_path = listing_url.split('/file/')[1].split('?')[0]
    dataset_id = listing_url.split('datasetid=')[1]
    download_url = f'https://redistrictingdatahub.org/wp-json/download/file/{file_path}'
    download_params = {'username': username, 'password': password, 'datasetid': dataset_id}

    download_response = requests.get(
        download_url, params=download_params, allow_redirects=True, timeout=120,
    )
    download_response.raise_for_status()

    with zipfile.ZipFile(io.BytesIO(download_response.content)) as zf:
        csv_files = [name for name in zf.namelist() if name.endswith('.csv')]
        if len(csv_files) != 1:
            raise ValueError(f'Expected 1 CSV in zip, found: {csv_files}')
        with zf.open(csv_files[0]) as csv_file:
            return pd.read_csv(csv_file, low_memory=False)

def locality_CVAP_only(state_CVAP, countycode):
    #TODO: Move GEOID20 constant definition so it can be used here too
    state_CVAP['GEOID20'] = state_CVAP['GEOID20'].astype(str)
    locality_CVAP = state_CVAP[state_CVAP['GEOID20'].str.startswith(countycode)]
    return(locality_CVAP)

def pull_CVAP_data(
    statecode,
    county,
    census_year,
    census_apikey=None,
    rdh_username=None,
    rdh_password=None,
    state_lookup=STATE_LOOKUP,
    rdh_url=RDH_LIST_URL,
):
    """
    Given a statecode (i.e. MD or NY),
    and county (full name, must be capitalized properly),
    pull state CVAP data, 
    save off county data and tiger files

    """
    if census_apikey is None:
        census_apikey = _load_census_key()
    if census_apikey is None:
        raise ValueError('No census key available. Please request one from the census to download census data. See README.')

    #TODO: Refactor this and pull census data so that tiger files not pulled twice
    #TODO: Refactor to reduce repeated code
    if rdh_username is None or rdh_password is None:
        loaded_username, loaded_password = _load_rdh_credentials()
        rdh_username = rdh_username or loaded_username
        rdh_password = rdh_password or loaded_password
    if rdh_username is None or rdh_password is None:
        raise ValueError(
            'No RDH credentials available. Run `python run.py secret set rdh`. See README.'
        )
    state = state_lookup.get(statecode)
    states_fips = get_all_states_fips_codes(census_year, census_apikey)  # get all fips codes for all states
    fipscode2 = states_fips[state]

    counties_codes = get_all_state_county_codes(fipscode2, census_year, census_apikey)  # get all county codes
    countycode = get_county_code(county, counties_codes)
    county_ST = county.replace(' ','_')+ '_' + statecode

    fipscode5 = fipscode2 + countycode
    state_CVAP = pull_state_CVAP_data(state, rdh_username, rdh_password, census_year, rdh_url)
    locality_CVAP = locality_CVAP_only(state_CVAP, fipscode5)
    
    if locality_CVAP.shape[0] == 0:
        raise ValueError(f'{county} data not in {state} CVAP data')

    save_CVAP_data(locality_CVAP, census_year, county_ST)

    for geo in (BLOCK_GEO, BLOCK_GROUP_GEO):
        # pull tiger files
        print(f"Now pulling tiger data for {geo} geography")
        pull_tiger_file(state, fipscode2, county_ST, countycode, geo, census_year)
    return "Success"

# pylint: disable-next=invalid-name
def save_RDH_predicted_vap_data(df, location, filename):
    '''Write county-filtered VAP projection data to its canonical directory.

    Args:
        df: DataFrame to save.
        location: Location identifier, e.g. 'Gwinnett_County_GA'.
        filename: Filename to save under, preserving the RDH naming convention
            (e.g. 'ga_vap_proj_2026_2035_b.csv').

    Returns:
        Path to the written CSV.
    '''
    dirname = build_RDH_predicted_vap_dir_path(location)
    if not os.path.exists(dirname):
        os.makedirs(dirname)
    # os.path.basename strips any directory prefix from the RDH zip entry name,
    # ensuring we only use the bare filename when writing locally.
    fpath = os.path.join(dirname, os.path.basename(filename))
    df.to_csv(fpath, index=False)
    return fpath


def locality_predicted_vap_only(state_vap_df, fipscode5):
    '''Filter a state-wide block-level VAP projection DataFrame to a single county.

    Args:
        state_vap_df: Block-level VAP projection DataFrame with a GEOID column.
        fipscode5: 5-digit FIPS code (state + county) used as a GEOID prefix filter.

    Returns:
        Filtered DataFrame containing only rows for the specified county.
    '''
    state_vap_df = state_vap_df.copy()
    # GEOID may be read as int from the CSV; cast to str so startswith works correctly.
    state_vap_df['GEOID'] = state_vap_df['GEOID'].astype(str)
    return state_vap_df[state_vap_df['GEOID'].str.startswith(fipscode5)]


# pylint: disable-next=invalid-name
def pull_RDH_predicted_vap_data(
    statecode,
    county,
    census_year,
    census_apikey=None,
    rdh_username=None,
    rdh_password=None,
    state_lookup=None,
    rdh_url=RDH_LIST_URL,
):
    '''Download block-level RDH predicted VAP (Voting Age Population) projection data for a county.

    Downloads the state block projection file from the RDH API (one file per state,
    one row per block), filters it to the specified county using the 5-digit FIPS code,
    and saves the result to the canonical on-disk location
    (datasets/census/RDH_predicted_vap/<location>/).

    Block-level projection files are identified by a ``_b`` suffix immediately before
    the file extension in the URL (e.g. ``ga_vap_proj_2026_2035_b.csv``). County-level
    projections use ``_cnty`` and are excluded.

    Args:
        statecode: Two-letter US state code, e.g. 'GA'.
        county: Full county name with proper capitalization, e.g. 'Gwinnett County'.
        census_year: Decennial census base year string, e.g. '2020'. Used to look up
            state and county FIPS codes via the Census API.
        census_apikey: Census API key for FIPS lookups. If None, resolved from the
            CENSUS_API_KEY env var or credentials.json.
        rdh_username: RDH API username. If None, resolved from env vars or credentials.json.
        rdh_password: RDH API password. If None, resolved from env vars or credentials.json.
        state_lookup: Mapping of state codes to full state names. Defaults to STATE_LOOKUP.
        rdh_url: RDH list endpoint. Defaults to RDH_LIST_URL.

    Returns:
        The string 'Success' on completion.

    Raises:
        ValueError: If credentials are missing, the county is not found in the state data,
            or no block-level VAP projection file exists in the RDH catalog.
    '''
    # --- Credential resolution ---
    # Each credential falls back to environment variables, then credentials.json,
    # so callers don't need to pass secrets explicitly in normal usage.
    if state_lookup is None:
        state_lookup = STATE_LOOKUP
    if census_apikey is None:
        census_apikey = _load_census_key()
    if census_apikey is None:
        raise ValueError(
            'No census key available. Please request one from the census to download census data. '
            'See README.'
        )

    if rdh_username is None or rdh_password is None:
        loaded_username, loaded_password = _load_rdh_credentials()
        rdh_username = rdh_username or loaded_username
        rdh_password = rdh_password or loaded_password
    if rdh_username is None or rdh_password is None:
        raise ValueError(
            'No RDH credentials available. Run `python run.py secret set rdh`. See README.'
        )

    # --- FIPS code lookup ---
    # We need the 2-digit state code and 3-digit county code to build the 5-digit FIPS
    # prefix used to filter the state-wide block file down to the target county.
    state = state_lookup.get(statecode)
    states_fips = get_all_states_fips_codes(census_year, census_apikey)
    fipscode2 = states_fips[state]

    counties_codes = get_all_state_county_codes(fipscode2, census_year, census_apikey)
    countycode = get_county_code(county, counties_codes)
    # county_st is the location key used for the on-disk directory (e.g. 'Gwinnett_County_GA').
    county_st = county.replace(' ', '_') + '_' + statecode

    # --- RDH catalog query ---
    # 'vap_proj' is the RDH keyword for Voting Age Population projection datasets.
    list_params = {
        'username': rdh_username,
        'password': rdh_password,
        'format': 'csv',
        'states': state,
        'keywords': 'vap_proj',
    }
    list_response = requests.get(rdh_url, params=list_params, timeout=60)
    catalog = pd.read_csv(io.StringIO(list_response.content.decode('utf-8')))

    # Block-level files have '_b' immediately before the extension (e.g. 'ga_vap_proj_2026_2035_b.csv').
    # County-level summaries use '_cnty' and cover a different unit of analysis.
    candidates = catalog[
        catalog['URL'].str.contains(r'_b\.', na=False, regex=True)
        & (catalog['Format'] == 'CSV')
    ].copy()

    if candidates.shape[0] == 0:
        raise ValueError(
            f'No block-level VAP projection CSV found for {state} in the RDH catalog.'
        )
    if candidates.shape[0] > 1:
        raise ValueError(
            f'Multiple block-level VAP projection files found for {state}: '
            f'{list(candidates["Title"])}'
        )

    # --- Download ---
    # The listing URL contains both the file path and the dataset ID needed for the
    # authenticated download endpoint.
    listing_url = candidates.iloc[0]['URL']
    file_path = listing_url.split('/file/')[1].split('?')[0]
    dataset_id = listing_url.split('datasetid=')[1]
    download_url = f'https://redistrictingdatahub.org/wp-json/download/file/{file_path}'
    download_params = {'username': rdh_username, 'password': rdh_password, 'datasetid': dataset_id}

    download_response = requests.get(
        download_url, params=download_params, allow_redirects=True, timeout=120,
    )
    download_response.raise_for_status()

    # --- Extract CSV from zip ---
    # RDH delivers each dataset as a single-file zip; we validate that assumption here.
    with zipfile.ZipFile(io.BytesIO(download_response.content)) as zf:
        csv_files = [name for name in zf.namelist() if name.endswith('.csv')]
        if len(csv_files) != 1:
            raise ValueError(f'Expected 1 CSV in zip, found: {csv_files}')
        filename = csv_files[0]
        with zf.open(filename) as csv_file:
            block_df = pd.read_csv(csv_file, low_memory=False)

    # --- Filter to county and save ---
    fipscode5 = fipscode2 + countycode
    locality_vap_df = locality_predicted_vap_only(block_df, fipscode5)

    if locality_vap_df.shape[0] == 0:
        raise ValueError(f'{county} data not in {state} VAP projection data')

    save_RDH_predicted_vap_data(locality_vap_df, county_st, filename)

    return 'Success'



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


