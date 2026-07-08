"""
Experimental: download RDH VAP projection data using Playwright browser automation.

The RDH /download/ endpoint requires a browser session cookie that cannot be
obtained via the requests library (wp-login.php returns 403 for non-browser
clients). Playwright drives a real Chromium instance to log in and download.

Usage (inside dev container):
    python -m python.scripts.pull_rdh_vap_playwright GA "Gwinnett County" 2020
"""

import argparse
import io
import os
import zipfile

import pandas as pd
import requests

from playwright.sync_api import sync_playwright

from python.utils.directory_constants import RDH_PREDICTED_VAP_FOLDER_NAME
from python.utils.pull_census_data import (
    VAP_PROJ_BLOCK_DATASET_IDS,
    RDH_DOWNLOAD_URL,
    _load_rdh_credentials,
    _load_census_key,
    get_all_states_fips_codes,
    get_all_state_county_codes,
    get_county_code,
    locality_predicted_vap_only,
    save_RDH_predicted_vap_data,
    STATE_LOOKUP,
)

DATASETS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    'datasets', 'census', RDH_PREDICTED_VAP_FOLDER_NAME,
)


def pull_rdh_vap_playwright(statecode, county, census_year):
    """Download RDH block-level VAP projection data for a county via Playwright.

    Args:
        statecode: Two-letter state code, e.g. 'GA'.
        county: Full county name, e.g. 'Gwinnett County'.
        census_year: Census base year string, e.g. '2020'.
    """
    rdh_username, rdh_password = _load_rdh_credentials()
    if not rdh_username or not rdh_password:
        raise ValueError('No RDH credentials. Run `python run.py secret set rdh`.')

    census_apikey = _load_census_key()
    if not census_apikey:
        raise ValueError('No census key. Run `python run.py secret set census`.')

    if statecode not in VAP_PROJ_BLOCK_DATASET_IDS:
        raise ValueError(f'No block-level VAP projection dataset available for {statecode}.')
    dataset_id = VAP_PROJ_BLOCK_DATASET_IDS[statecode]
    document = f'/web_ready_stage/projections/2026_2035/{statecode.lower()}_vap_proj_2026_2035_b.zip'

    # FIPS lookup for county filtering
    state = STATE_LOOKUP.get(statecode)
    states_fips = get_all_states_fips_codes(census_year, census_apikey)
    fipscode2 = states_fips[state]
    counties_codes = get_all_state_county_codes(fipscode2, census_year, census_apikey)
    countycode = get_county_code(county, counties_codes)
    fipscode5 = fipscode2 + countycode
    county_st = county.replace(' ', '_') + '_' + statecode

    download_url = f'{RDH_DOWNLOAD_URL}?datasetid={dataset_id}&document={document}'
    print(f'Logging in to RDH and downloading: {download_url}')

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # RDH uses /login/ (not /wp-login.php); field names are username/password
        page.goto('https://redistrictingdatahub.org/login/', timeout=30000)
        page.fill('[name="username"]', rdh_username)
        page.fill('[name="password"]', rdh_password)
        with page.expect_navigation(timeout=30000):
            page.click('[name="login"]')

        if '/login/' in page.url:
            raise ValueError('RDH login failed — check credentials or login page structure changed.')

        # The confirmation page renders a pre-signed S3 link as the "Download" anchor.
        # networkidle ensures JS has fully rendered the link before we extract it.
        page.goto(download_url, wait_until='networkidle', timeout=60000)
        presigned_url = page.evaluate('''
            () => {
                const links = Array.from(document.querySelectorAll('a'));
                const link = links.find(el => el.innerText && el.innerText.trim().match(/^Download$/i));
                return link ? link.href : null;
            }
        ''')
        browser.close()
        if not presigned_url:
            raise ValueError('Download link not found on RDH confirmation page.')
        print(f'Downloading {statecode} VAP projection data...')

    response = requests.get(presigned_url, timeout=300)
    response.raise_for_status()
    zip_bytes = io.BytesIO(response.content)

    # Extract CSV from zip and filter to county
    with zipfile.ZipFile(zip_bytes) as zf:
        csv_files = [name for name in zf.namelist() if name.endswith('.csv')]
        if len(csv_files) != 1:
            raise ValueError(f'Expected 1 CSV in zip, found: {csv_files}')
        filename = csv_files[0]
        with zf.open(filename) as csv_file:
            block_df = pd.read_csv(csv_file, low_memory=False)

    locality_vap_df = locality_predicted_vap_only(block_df, fipscode5)
    if locality_vap_df.shape[0] == 0:
        raise ValueError(f'{county} data not found in {state} VAP projection data.')

    save_RDH_predicted_vap_data(locality_vap_df, county_st, filename)
    print(f'Saved {len(locality_vap_df)} rows to datasets/census/{RDH_PREDICTED_VAP_FOLDER_NAME}/{county_st}/')
    return 'Success'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Download RDH VAP projection data via browser automation.')
    parser.add_argument('state', help='Two-letter state code (e.g. GA)')
    parser.add_argument('county', help='Full county name (e.g. "Gwinnett County")')
    parser.add_argument('census_year', help='Census base year (e.g. 2020)')
    args = parser.parse_args()
    result = pull_rdh_vap_playwright(args.state, args.county, args.census_year)
    print(result)
