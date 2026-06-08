"""Tests for unzip_file() and pull_tiger_file() in pull_census_data."""

import zipfile
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
import requests

from python.utils.pull_census_data import pull_tiger_file, unzip_file, _is_retryable_http_error
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
