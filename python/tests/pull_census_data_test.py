''' Tests for pull_census_data utility functions. '''

# pylint: disable=invalid-name
# CVAP is an established acronym used throughout the codebase; disabling to allow it in function names.

import io
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import requests

import python.utils.pull_census_data as pcd
from python.utils.pull_census_data import (
    pull_state_CVAP_data,
    pull_tiger_file,
    unzip_file,
    _is_retryable_http_error,
    _request_with_retries,
    HTTP_MAX_RETRIES,
    HTTP_RETRY_BACKOFF_SECONDS,
    get_census_json,
    download_file,
    pull_RDH_predicted_vap_data,
    HTTP_TIMEOUT_SECONDS,
)
from python.utils.directory_constants import BLOCK_GEO


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
    ''' Selects the most recent year in the census window, excluding years before census_year. '''
    list_bytes = _make_list_response_bytes([
        _block_level_row('2019'),
        _block_level_row('2020'),
        _block_level_row('2021'),
    ])
    zip_bytes = _make_cvap_zip_bytes('2021')

    with patch('python.utils.pull_census_data.requests.get', side_effect=_mock_get(list_bytes, zip_bytes)) as mock_get:
        result = pull_state_CVAP_data('Georgia', 'user', 'pass', '2020', rdh_url=TEST_RDH_URL)

    assert isinstance(result, pd.DataFrame)
    download_url = mock_get.call_args_list[1][0][0]
    assert 'ga_cvap_2021' in download_url


def test_pull_state_CVAP_data_selects_most_recent_in_census_window():
    ''' Selects the most recent CVAP dataset within the census decade when no exact-year match exists. '''
    list_bytes = _make_list_response_bytes([
        _block_level_row('2023'),
        _block_level_row('2025'),
    ])
    zip_bytes = _make_cvap_zip_bytes('2025')

    with patch('python.utils.pull_census_data.requests.get', side_effect=_mock_get(list_bytes, zip_bytes)) as mock_get:
        result = pull_state_CVAP_data('Georgia', 'user', 'pass', '2020', rdh_url=TEST_RDH_URL)

    assert isinstance(result, pd.DataFrame)
    download_url = mock_get.call_args_list[1][0][0]
    assert 'ga_cvap_2025' in download_url


def test_pull_state_CVAP_data_excludes_next_census_decade():
    ''' Does not select a dataset from the next census decade (e.g. 2030+) when census_year is 2020. '''
    list_bytes = _make_list_response_bytes([
        _block_level_row('2025'),
        _block_level_row('2030'),
    ])
    zip_bytes = _make_cvap_zip_bytes('2025')

    with patch('python.utils.pull_census_data.requests.get', side_effect=_mock_get(list_bytes, zip_bytes)) as mock_get:
        result = pull_state_CVAP_data('Georgia', 'user', 'pass', '2020', rdh_url=TEST_RDH_URL)

    assert isinstance(result, pd.DataFrame)
    download_url = mock_get.call_args_list[1][0][0]
    assert 'ga_cvap_2025' in download_url
    assert 'ga_cvap_2030' not in download_url


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


def _make_http_error(status):
    """Build a requests.HTTPError carrying a response with the given status."""
    response = requests.Response()
    response.status_code = status
    return requests.exceptions.HTTPError(response=response)


class TestIsRetryableHttpError:
    """Tests for _is_retryable_http_error()."""

    def test_5xx_is_retryable(self):
        assert _is_retryable_http_error(_make_http_error(500)) is True
        assert _is_retryable_http_error(_make_http_error(503)) is True
        assert _is_retryable_http_error(_make_http_error(520)) is True

    def test_4xx_is_not_retryable(self):
        assert _is_retryable_http_error(_make_http_error(401)) is False
        assert _is_retryable_http_error(_make_http_error(404)) is False

    def test_no_response_is_not_retryable(self):
        assert _is_retryable_http_error(requests.exceptions.HTTPError()) is False


class TestUnzipFile:
    """Tests for unzip_file()."""

    def test_extracts_contents(self, tmp_path):
        """Zip with a known file is extracted to outdir with the same content."""
        zip_path = tmp_path / 'sample.zip'
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('hello.txt', 'world')
        outdir = tmp_path / 'out'
        outdir.mkdir()

        unzip_file(zip_path, outdir)

        extracted = outdir / 'hello.txt'
        assert extracted.exists()
        assert extracted.read_text() == 'world'

    def test_removes_zip_after_extract(self, tmp_path):
        """The source zip file is deleted after successful extraction."""
        zip_path = tmp_path / 'sample.zip'
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.writestr('hello.txt', 'world')
        outdir = tmp_path / 'out'
        outdir.mkdir()

        unzip_file(zip_path, outdir)

        assert not zip_path.exists()

    def test_raises_on_corrupt_zip(self, tmp_path):
        """A corrupt zip file raises zipfile.BadZipFile."""
        bad_path = tmp_path / 'bad.zip'
        bad_path.write_bytes(b'not a zip file')
        outdir = tmp_path / 'out'
        outdir.mkdir()

        with pytest.raises(zipfile.BadZipFile):
            unzip_file(bad_path, outdir)


class TestPullTigerFile:
    """Tests for pull_tiger_file()."""

    def test_skips_download_when_shapefile_already_exists(self, tmp_path):
        """Does not call download_file when the expected .shp file is already on disk."""
        (tmp_path / 'tl_2020_48439_tabblock20.shp').touch()

        with patch('python.utils.pull_census_data.build_tiger_location_dir', return_value=str(tmp_path)), \
             patch('python.utils.pull_census_data.download_file') as mock_download:
            pull_tiger_file(
                state='Texas',
                fips='48',
                county_st='Tarrant_County_TX',
                county_code='439',
                geo=BLOCK_GEO,
                census_year='2020',
            )

        mock_download.assert_not_called()

    def test_uses_absolute_tiger_dir(self, tmp_path):
        """pull_tiger_file writes into the directory returned by build_tiger_location_dir."""
        captured = {}

        def fake_download(url, local_dir):
            captured['url'] = url
            captured['local_dir'] = local_dir
            return Path(local_dir) / 'fake.zip'

        def fake_unzip(fpath, outdir):
            captured['unzip_fpath'] = fpath
            captured['unzip_outdir'] = outdir

        with patch('python.utils.pull_census_data.build_tiger_location_dir', return_value=str(tmp_path)), \
             patch('python.utils.pull_census_data.download_file', side_effect=fake_download), \
             patch('python.utils.pull_census_data.unzip_file', side_effect=fake_unzip):
            pull_tiger_file(
                state='Texas',
                fips='48',
                county_st='Tarrant_County_TX',
                county_code='439',
                geo=BLOCK_GEO,
                census_year='2020',
            )

        assert Path(captured['local_dir']) == tmp_path
        assert Path(captured['unzip_outdir']) == tmp_path


class TestRequestWithRetries:
    """Tests for _request_with_retries()."""

    def _no_sleep(self, _seconds):
        return None

    def test_returns_on_first_success(self):
        calls = []

        def operation():
            calls.append(1)
            return 'ok'

        assert _request_with_retries(operation, 'x', sleep=self._no_sleep) == 'ok'
        assert len(calls) == 1

    def test_retries_transient_then_succeeds(self):
        calls = []
        sleeps = []

        def operation():
            calls.append(1)
            if len(calls) < 2:
                raise requests.exceptions.ConnectionError('boom')
            return 'ok'

        assert _request_with_retries(operation, 'x', sleep=sleeps.append) == 'ok'
        assert len(calls) == 2
        assert sleeps == [HTTP_RETRY_BACKOFF_SECONDS]

    def test_non_retryable_http_error_raises_immediately(self):
        calls = []

        def operation():
            calls.append(1)
            raise _make_http_error(404)

        with pytest.raises(requests.exceptions.HTTPError):
            _request_with_retries(operation, 'x', sleep=self._no_sleep)
        assert len(calls) == 1

    def test_exhausts_retries_and_raises_last_error(self):
        calls = []

        def operation():
            calls.append(1)
            raise requests.exceptions.Timeout('slow')

        with pytest.raises(requests.exceptions.Timeout):
            _request_with_retries(operation, 'x', sleep=self._no_sleep)
        assert len(calls) == HTTP_MAX_RETRIES


class TestDownloadFileRetry:
    """Tests for download_file() retry behavior."""

    def _response_cm(self, response):
        cm = MagicMock()
        cm.__enter__.return_value = response
        cm.__exit__.return_value = False
        return cm

    def test_retries_mid_stream_break_and_overwrites_partial(self, tmp_path):
        def broken_stream():
            yield b'partial-bytes'
            raise requests.exceptions.ChunkedEncodingError('connection broken')

        bad_response = MagicMock()
        bad_response.raise_for_status.return_value = None
        bad_response.iter_content.return_value = broken_stream()

        good_response = MagicMock()
        good_response.raise_for_status.return_value = None
        good_response.iter_content.return_value = [b'hello ', b'world']

        with patch(
            'python.utils.pull_census_data.requests.get',
            side_effect=[self._response_cm(bad_response), self._response_cm(good_response)],
        ), patch('python.utils.pull_census_data.time.sleep', return_value=None):
            result = download_file('http://example/tl_x.zip', tmp_path)

        assert Path(result).read_bytes() == b'hello world'


class TestLoadRdhCredentials:
    """Tests for _load_rdh_credentials()."""

    def test_reads_from_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv('RDH_USERNAME', 'env-user')
        monkeypatch.setenv('RDH_PASSWORD', 'env-pass')
        from python.utils.pull_census_data import _load_rdh_credentials
        assert _load_rdh_credentials(tmp_path / 'missing.json') == ('env-user', 'env-pass')

    def test_reads_from_file(self, monkeypatch, tmp_path):
        monkeypatch.delenv('RDH_USERNAME', raising=False)
        monkeypatch.delenv('RDH_PASSWORD', raising=False)
        creds = tmp_path / 'credentials.json'
        creds.write_text('{"rdh_username": "file-user", "rdh_password": "file-pass"}', encoding='utf-8')
        from python.utils.pull_census_data import _load_rdh_credentials
        assert _load_rdh_credentials(creds) == ('file-user', 'file-pass')

    def test_env_username_file_password(self, monkeypatch, tmp_path):
        monkeypatch.setenv('RDH_USERNAME', 'env-user')
        monkeypatch.delenv('RDH_PASSWORD', raising=False)
        creds = tmp_path / 'credentials.json'
        creds.write_text('{"rdh_password": "file-pass"}', encoding='utf-8')
        from python.utils.pull_census_data import _load_rdh_credentials
        assert _load_rdh_credentials(creds) == ('env-user', 'file-pass')

    def test_none_when_absent(self, monkeypatch, tmp_path):
        monkeypatch.delenv('RDH_USERNAME', raising=False)
        monkeypatch.delenv('RDH_PASSWORD', raising=False)
        from python.utils.pull_census_data import _load_rdh_credentials
        assert _load_rdh_credentials(tmp_path / 'missing.json') == (None, None)


def test_pull_CVAP_data_raises_when_rdh_credentials_missing(monkeypatch):
    ''' pull_CVAP_data fails fast (before any network call) when RDH creds are absent. '''
    monkeypatch.setattr(pcd, '_load_rdh_credentials', lambda *a, **k: (None, None))
    with pytest.raises(ValueError, match='No RDH credentials available'):
        pcd.pull_CVAP_data('GA', 'Gwinnett County', '2020', census_apikey='fake-key')


class TestGetCensusJson:
    """Tests for get_census_json()."""

    def test_returns_parsed_json(self):
        ok = MagicMock()
        ok.raise_for_status.return_value = None
        ok.json.return_value = [['NAME', 'state'], ['Texas', '48']]
        with patch('python.utils.pull_census_data.requests.get', return_value=ok):
            result = get_census_json('http://example/api')
        assert result == [['NAME', 'state'], ['Texas', '48']]

    def test_retries_on_5xx_then_succeeds(self):
        bad = MagicMock()
        bad.raise_for_status.side_effect = _make_http_error(503)
        ok = MagicMock()
        ok.raise_for_status.return_value = None
        ok.json.return_value = {'ok': True}
        with patch('python.utils.pull_census_data.requests.get', side_effect=[bad, ok]), \
             patch('python.utils.pull_census_data.time.sleep', return_value=None):
            result = get_census_json('http://example/api')
        assert result == {'ok': True}


def _make_vap_zip_bytes(matching_geoid, non_matching_geoid):
    ''' Returns a minimal RDH VAP projection zip file in memory containing one CSV. '''
    header = 'GEOID,STATEFP,COUNTYFP,STATE,COUNTY,Projected_TotalPop_VAP_2026'
    csv_content = (
        header + '\n'
        f'{matching_geoid},13,135,Georgia,Gwinnett County,30\n'
        f'{non_matching_geoid},48,453,Texas,Travis County,10\n'
    )
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w') as zf:
        zf.writestr('ga_vap_proj_2026_2035_b.csv', csv_content)
    return zip_buffer.getvalue()


def _make_mock_playwright_page(url='https://redistrictingdatahub.org/download/?datasetid=54445',
                                evaluate_return='https://s3.example.com/presigned-download-url'):
    ''' Returns (mock_sync_playwright, mock_page) wired so `with sync_playwright() as p:
    browser = p.chromium.launch(...); page = browser.new_page()` yields mock_page. '''
    mock_page = MagicMock()
    mock_page.url = url
    mock_page.evaluate.return_value = evaluate_return

    mock_browser = MagicMock()
    mock_browser.new_page.return_value = mock_page

    mock_chromium = MagicMock()
    mock_chromium.launch.return_value = mock_browser

    mock_playwright_ctx = MagicMock()
    mock_playwright_ctx.chromium = mock_chromium

    mock_sync_playwright = MagicMock()
    mock_sync_playwright.return_value.__enter__.return_value = mock_playwright_ctx

    return mock_sync_playwright, mock_page


class TestPullRDHPredictedVapData:
    ''' Unit tests for pull_RDH_predicted_vap_data: credential/state validation fail fast
    without network calls; the download path (Playwright login + requests.get + zip extract +
    county filter + save) is exercised with Playwright and HTTP fully mocked. '''

    def test_raises_when_census_apikey_missing(self, monkeypatch):
        ''' Fails fast, before any network call, when no census API key is available. '''
        monkeypatch.setattr(pcd, '_load_census_key', lambda *a, **k: None)
        with pytest.raises(ValueError, match='No census key available'):
            pull_RDH_predicted_vap_data('GA', 'Gwinnett County', '2020')

    def test_raises_when_rdh_credentials_missing(self, monkeypatch):
        ''' Fails fast, before any network call, when RDH credentials are absent. '''
        monkeypatch.setattr(pcd, '_load_rdh_credentials', lambda *a, **k: (None, None))
        with pytest.raises(ValueError, match='No RDH credentials available'):
            pull_RDH_predicted_vap_data('GA', 'Gwinnett County', '2020', census_apikey='fake-key')

    def test_raises_for_state_without_block_level_projection(self, monkeypatch):
        ''' CT has no block-level VAP projection dataset; rejected after FIPS resolution,
        before any Playwright/HTTP call. '''
        monkeypatch.setattr(
            pcd, '_resolve_location_fips',
            lambda *a, **k: ('Connecticut', '09', '001', '09001', 'Fairfield_County_CT'),
        )
        with pytest.raises(ValueError, match='No block-level VAP projection dataset available for CT'):
            pull_RDH_predicted_vap_data(
                'CT', 'Fairfield County', '2020',
                census_apikey='fake-key', rdh_username='user', rdh_password='pass',
            )

    def test_raises_when_login_fails(self, monkeypatch):
        ''' Raises ValueError when the RDH page URL still contains /login/ after the click,
        indicating the login attempt failed. '''
        mock_sync_playwright, _ = _make_mock_playwright_page(
            url='https://redistrictingdatahub.org/login/',
        )
        monkeypatch.setattr(pcd, '_resolve_location_fips', lambda *a, **k: (
            'Georgia', '13', '135', '13135', 'Gwinnett_County_GA',
        ))
        with patch('playwright.sync_api.sync_playwright', mock_sync_playwright), \
             pytest.raises(ValueError, match='RDH login failed'):
            pull_RDH_predicted_vap_data(
                'GA', 'Gwinnett County', '2020',
                census_apikey='fake-key', rdh_username='user', rdh_password='pass',
            )

    def test_raises_when_download_link_not_found(self, monkeypatch):
        ''' Raises ValueError when no presigned download link is found on the confirmation page. '''
        mock_sync_playwright, _ = _make_mock_playwright_page(evaluate_return=None)
        monkeypatch.setattr(pcd, '_resolve_location_fips', lambda *a, **k: (
            'Georgia', '13', '135', '13135', 'Gwinnett_County_GA',
        ))
        with patch('playwright.sync_api.sync_playwright', mock_sync_playwright), \
             pytest.raises(ValueError, match='Download link not found'):
            pull_RDH_predicted_vap_data(
                'GA', 'Gwinnett County', '2020',
                census_apikey='fake-key', rdh_username='user', rdh_password='pass',
            )

    def test_raises_when_locality_not_in_state_data(self, monkeypatch):
        ''' Raises ValueError when no rows in the downloaded state file match the county's FIPS prefix. '''
        zip_bytes = _make_vap_zip_bytes(matching_geoid='484530501053055', non_matching_geoid='484539999999999')
        download_resp = MagicMock()
        download_resp.content = zip_bytes
        download_resp.raise_for_status = MagicMock()

        mock_sync_playwright, _ = _make_mock_playwright_page()
        monkeypatch.setattr(pcd, '_resolve_location_fips', lambda *a, **k: (
            'Georgia', '13', '135', '13135', 'Gwinnett_County_GA',
        ))
        with patch('playwright.sync_api.sync_playwright', mock_sync_playwright), \
             patch('python.utils.pull_census_data.requests.get', return_value=download_resp), \
             pytest.raises(ValueError, match='data not in'):
            pull_RDH_predicted_vap_data(
                'GA', 'Gwinnett County', '2020',
                census_apikey='fake-key', rdh_username='user', rdh_password='pass',
            )

    def test_returns_success_and_saves_filtered_csv(self, tmp_path, monkeypatch):
        ''' Happy path: Playwright login, presigned download, zip extract, county filter, save.
        Verifies credentials reach the login form, the download URL is requested once, and only
        the row matching the county's FIPS prefix is written to disk. '''
        zip_bytes = _make_vap_zip_bytes(matching_geoid='131350501053055', non_matching_geoid='484530501053055')
        download_resp = MagicMock()
        download_resp.content = zip_bytes
        download_resp.raise_for_status = MagicMock()

        mock_sync_playwright, mock_page = _make_mock_playwright_page()
        monkeypatch.setattr(pcd, '_resolve_location_fips', lambda *a, **k: (
            'Georgia', '13', '135', '13135', 'Gwinnett_County_GA',
        ))
        monkeypatch.setattr(pcd, 'build_RDH_predicted_vap_dir_path', lambda location: str(tmp_path))

        with patch('playwright.sync_api.sync_playwright', mock_sync_playwright), \
             patch('python.utils.pull_census_data.requests.get', return_value=download_resp) as mock_get:
            result = pull_RDH_predicted_vap_data(
                'GA', 'Gwinnett County', '2020',
                census_apikey='fake-key', rdh_username='user', rdh_password='pass',
            )

        assert result == 'Success'
        mock_page.fill.assert_any_call('[name="username"]', 'user')
        mock_page.fill.assert_any_call('[name="password"]', 'pass')
        mock_get.assert_called_once_with('https://s3.example.com/presigned-download-url', timeout=HTTP_TIMEOUT_SECONDS)

        saved_files = list(tmp_path.glob('*.csv'))
        assert len(saved_files) == 1
        saved_df = pd.read_csv(saved_files[0])
        assert saved_df['GEOID'].astype(str).tolist() == ['131350501053055']
