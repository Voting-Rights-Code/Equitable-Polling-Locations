''' Tests for pull_census_data utility functions. '''

# pylint: disable=invalid-name
# CVAP is an established acronym used throughout the codebase; disabling to allow it in function names.

import io
import zipfile

import pandas as pd
import pytest
from unittest.mock import MagicMock, patch

from python.utils.pull_census_data import pull_state_CVAP_data


TEST_RDH_URL = 'https://redistrictingdatahub.org/wp-json/download/list'


def _make_list_response_bytes(rows):
    ''' Returns a CSV-encoded list API response as bytes given a list of row dicts. '''
    return pd.DataFrame(rows).to_csv(index=False).encode('utf-8')


def _block_level_row(year='2020', fmt='CSV'):
    ''' Returns a single catalog row matching the block-level CVAP dataset pattern. '''
    return {
        'State': 'Georgia',
        'Title': f'Georgia CVAP Data Disaggregated to the 2020 Block Level ({year})',
        'Source': 'RDH',
        'Format': fmt,
        'SizeMB': 1.0,
        'Updated': '2023-01-01',
        'Filename': f'ga_cvap_{year}_2020_b.zip',
        'URL': (
            f'https://redistrictingdatahub.org/wp-json/download/file/'
            f'web_ready_stage%2Fga_cvap_{year}_2020_b.zip'
            f'?username=YOURUSERNAME&password=YOURPASSWORD&datasetid=99999'
        ),
    }


def _make_cvap_zip_bytes(year='2020'):
    ''' Returns a minimal CVAP zip file in memory containing one CSV. '''
    suffix = year[-2:]
    header = f'GEOID20,CVAP_TOT{suffix},CVAP_HSP{suffix},CVAP_NHS{suffix},' \
             f'CVAP_WHT{suffix},CVAP_BLA{suffix},CVAP_AMI{suffix},' \
             f'CVAP_ASI{suffix},CVAP_NHP{suffix},CVAP_2OM{suffix}'
    csv_content = header + '\n130019501001000,9,0,9,9,0,0,0,0,0\n'

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zf:
        zf.writestr(f'ga_cvap_{year}_2020_b.csv', csv_content)
    return zip_buffer.getvalue()


def _mock_get(list_bytes, zip_bytes):
    ''' Returns a side_effect list for two sequential requests.get calls. '''
    list_resp = MagicMock()
    list_resp.content = list_bytes

    download_resp = MagicMock()
    download_resp.content = zip_bytes
    download_resp.raise_for_status = MagicMock()

    return [list_resp, download_resp]


def test_pull_state_CVAP_data_returns_dataframe():
    ''' Returns a DataFrame when the API returns exactly one matching block-level CSV. '''
    list_bytes = _make_list_response_bytes([_block_level_row('2020')])
    zip_bytes = _make_cvap_zip_bytes('2020')

    with patch('python.utils.pull_census_data.requests.get', side_effect=_mock_get(list_bytes, zip_bytes)):
        result = pull_state_CVAP_data('Georgia', 'user', 'pass', '2020', rdh_url=TEST_RDH_URL)

    assert isinstance(result, pd.DataFrame)
    assert result.shape[0] == 1
    assert 'GEOID20' in result.columns


def test_pull_state_CVAP_data_raises_when_no_dataset_found():
    ''' Raises ValueError when no block-level dataset matches the requested year. '''
    wrong_row = _block_level_row('2020')
    wrong_row['Title'] = 'Georgia Block Group CVAP Data (2020)'  # wrong geography
    list_bytes = _make_list_response_bytes([wrong_row])

    list_resp = MagicMock()
    list_resp.content = list_bytes

    with patch('python.utils.pull_census_data.requests.get', return_value=list_resp):
        with pytest.raises(ValueError, match='No block-level CVAP CSV found'):
            pull_state_CVAP_data('Georgia', 'user', 'pass', '2020', rdh_url=TEST_RDH_URL)


def test_pull_state_CVAP_data_raises_when_multiple_datasets_found():
    ''' Raises ValueError when the catalog contains more than one matching row. '''
    list_bytes = _make_list_response_bytes([
        _block_level_row('2020'),
        _block_level_row('2020'),
    ])

    list_resp = MagicMock()
    list_resp.content = list_bytes

    with patch('python.utils.pull_census_data.requests.get', return_value=list_resp):
        with pytest.raises(ValueError, match='Multiple block-level CVAP CSVs found'):
            pull_state_CVAP_data('Georgia', 'user', 'pass', '2020', rdh_url=TEST_RDH_URL)


def test_pull_state_CVAP_data_filters_by_year():
    ''' Returns data only for the requested year even when multiple years are in the catalog. '''
    list_bytes = _make_list_response_bytes([
        _block_level_row('2019'),
        _block_level_row('2020'),
        _block_level_row('2021'),
    ])
    zip_bytes = _make_cvap_zip_bytes('2020')

    with patch('python.utils.pull_census_data.requests.get', side_effect=_mock_get(list_bytes, zip_bytes)):
        result = pull_state_CVAP_data('Georgia', 'user', 'pass', '2020', rdh_url=TEST_RDH_URL)

    assert isinstance(result, pd.DataFrame)
    assert result.shape[0] == 1


def test_pull_state_CVAP_data_ignores_shp_format():
    ''' Does not select SHP rows even when Title matches, only CSV. '''
    list_bytes = _make_list_response_bytes([
        _block_level_row('2020', fmt='SHP'),
        _block_level_row('2020', fmt='CSV'),
    ])
    zip_bytes = _make_cvap_zip_bytes('2020')

    with patch('python.utils.pull_census_data.requests.get', side_effect=_mock_get(list_bytes, zip_bytes)):
        result = pull_state_CVAP_data('Georgia', 'user', 'pass', '2020', rdh_url=TEST_RDH_URL)

    assert isinstance(result, pd.DataFrame)
