"""Tests for unzip_file() and pull_tiger_file() in pull_census_data."""

import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import requests

from python.utils.pull_census_data import pull_tiger_file, unzip_file, _is_retryable_http_error, _request_with_retries, HTTP_MAX_RETRIES, get_census_json, download_file
from python.utils.directory_constants import BLOCK_GEO
from python.utils.utils import build_tiger_location_dir


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

    def test_uses_absolute_tiger_dir(self):
        """pull_tiger_file writes into the absolute build_tiger_location_dir, not a CWD-relative path."""
        captured = {}

        def fake_download(url, local_dir):
            captured['url'] = url
            captured['local_dir'] = local_dir
            # Return a fake zip path so unzip_file (also mocked) has something to receive.
            return Path(local_dir) / 'fake.zip'

        def fake_unzip(fpath, outdir):
            captured['unzip_fpath'] = fpath
            captured['unzip_outdir'] = outdir

        with patch('python.utils.pull_census_data.download_file', side_effect=fake_download), \
             patch('python.utils.pull_census_data.unzip_file', side_effect=fake_unzip):
            pull_tiger_file(
                state='Texas',
                fips='48',
                county_st='Tarrant_County_TX',
                county_code='439',
                geo=BLOCK_GEO,
                census_year='2020',
            )

        expected = Path(build_tiger_location_dir('Tarrant_County_TX'))
        assert Path(captured['local_dir']) == expected
        assert Path(captured['unzip_outdir']) == expected


class TestRequestWithRetries:
    """Tests for _request_with_retries()."""

    def _no_sleep(self, _seconds):
        return None

    def test_returns_on_first_success(self):
        calls = []

        def operation():
            calls.append(1)
            return "ok"

        assert _request_with_retries(operation, "x", sleep=self._no_sleep) == "ok"
        assert len(calls) == 1

    def test_retries_transient_then_succeeds(self):
        calls = []

        def operation():
            calls.append(1)
            if len(calls) < 2:
                raise requests.exceptions.ConnectionError("boom")
            return "ok"

        assert _request_with_retries(operation, "x", sleep=self._no_sleep) == "ok"
        assert len(calls) == 2

    def test_non_retryable_http_error_raises_immediately(self):
        calls = []

        def operation():
            calls.append(1)
            raise _make_http_error(404)

        with pytest.raises(requests.exceptions.HTTPError):
            _request_with_retries(operation, "x", sleep=self._no_sleep)
        assert len(calls) == 1

    def test_exhausts_retries_and_raises_last_error(self):
        calls = []

        def operation():
            calls.append(1)
            raise requests.exceptions.Timeout("slow")

        with pytest.raises(requests.exceptions.Timeout):
            _request_with_retries(operation, "x", sleep=self._no_sleep)
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


class TestGetCensusJson:
    """Tests for get_census_json()."""

    def test_returns_parsed_json(self):
        ok = MagicMock()
        ok.raise_for_status.return_value = None
        ok.json.return_value = [["NAME", "state"], ["Texas", "48"]]
        with patch('python.utils.pull_census_data.requests.get', return_value=ok):
            result = get_census_json('http://example/api')
        assert result == [["NAME", "state"], ["Texas", "48"]]

    def test_retries_on_5xx_then_succeeds(self):
        bad = MagicMock()
        bad.raise_for_status.side_effect = _make_http_error(503)
        ok = MagicMock()
        ok.raise_for_status.return_value = None
        ok.json.return_value = {"ok": True}
        with patch('python.utils.pull_census_data.requests.get', side_effect=[bad, ok]), \
             patch('python.utils.pull_census_data.time.sleep', return_value=None):
            result = get_census_json('http://example/api')
        assert result == {"ok": True}
