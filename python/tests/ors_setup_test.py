'''Tests for python/utils/ors_setup.py.'''
import os
from unittest.mock import patch

import pytest

from python.utils.ors_setup import (
    GEOFABRIK_BASE_URL,
    GEOFABRIK_STATE_SLUGS,
    ORS_DATA_DIR,
    STATE_CODE_TO_SLUG,
    download_pbf_if_missing,
    geofabrik_url,
    location_from_config_file,
    pbf_path,
    state_slug_from_location,
)


class TestSlugTable:
    '''Sanity checks on the GEOFABRIK_STATE_SLUGS set.'''

    def test_contains_all_50_states_plus_dc(self):
        '''The slug table should have exactly 51 entries (50 states + DC).'''
        assert len(GEOFABRIK_STATE_SLUGS) == 51

    def test_contains_georgia(self):
        assert 'georgia' in GEOFABRIK_STATE_SLUGS

    def test_contains_district_of_columbia(self):
        '''DC's Geofabrik slug is hyphenated, not abbreviated.'''
        assert 'district-of-columbia' in GEOFABRIK_STATE_SLUGS

    def test_contains_new_york_with_hyphen(self):
        '''Multi-word states use hyphens in their Geofabrik slugs.'''
        assert 'new-york' in GEOFABRIK_STATE_SLUGS

    def test_excludes_uppercase_postal_codes(self):
        '''Postal codes like "GA" must not appear; slugs only.'''
        assert 'GA' not in GEOFABRIK_STATE_SLUGS
        assert 'NY' not in GEOFABRIK_STATE_SLUGS


class TestGeofabrikUrl:
    '''Tests for ``geofabrik_url``.'''

    def test_builds_url_for_known_slug(self):
        assert geofabrik_url('georgia') == f'{GEOFABRIK_BASE_URL}/georgia-latest.osm.pbf'

    def test_builds_url_for_hyphenated_slug(self):
        assert geofabrik_url('new-york') == f'{GEOFABRIK_BASE_URL}/new-york-latest.osm.pbf'

    def test_raises_value_error_for_unknown_slug(self):
        with pytest.raises(ValueError, match='unknown state slug'):
            geofabrik_url('atlantis')


class TestPbfPath:
    '''Tests for ``pbf_path``.'''

    def test_returns_path_under_ors_data_dir(self):
        result = pbf_path('georgia')
        assert result.endswith(os.path.join('datasets', 'openrouteservice',
                                            'georgia-latest.osm.pbf'))
        assert ORS_DATA_DIR in result


class TestDownloadPbfIfMissing:
    '''Tests for ``download_pbf_if_missing``.'''

    def test_skips_download_when_file_present(self, tmp_path):
        '''If the target file already exists, urlretrieve must not be called.'''
        with patch('python.utils.ors_setup.ORS_DATA_DIR', str(tmp_path)):
            with patch('python.utils.ors_setup.pbf_path',
                       return_value=str(tmp_path / 'georgia-latest.osm.pbf')):
                target = tmp_path / 'georgia-latest.osm.pbf'
                target.write_bytes(b'fake pbf data')
                with patch('python.utils.ors_setup.urllib.request.urlretrieve') as mock_retrieve:
                    result = download_pbf_if_missing('georgia')
                    assert result == str(target)
                    mock_retrieve.assert_not_called()

    def test_calls_urlretrieve_when_file_absent(self, tmp_path):
        '''If the target file does not exist, urlretrieve must be called with a
        .partial path; on success the final file exists and no .partial remains.'''
        with patch('python.utils.ors_setup.ORS_DATA_DIR', str(tmp_path)):
            target_path = str(tmp_path / 'georgia-latest.osm.pbf')
            partial_path = f'{target_path}.partial'
            with patch('python.utils.ors_setup.pbf_path', return_value=target_path):
                def fake_retrieve(url, target):
                    del url
                    with open(target, 'wb') as fh:
                        fh.write(b'fake pbf data')
                with patch('python.utils.ors_setup.urllib.request.urlretrieve',
                           side_effect=fake_retrieve) as mock_retrieve:
                    result = download_pbf_if_missing('georgia')
                    assert result == target_path
                    mock_retrieve.assert_called_once()
                    args, _ = mock_retrieve.call_args
                    assert args[0] == f'{GEOFABRIK_BASE_URL}/georgia-latest.osm.pbf'
                    assert args[1] == partial_path
                    assert os.path.exists(target_path), 'final .pbf must exist'
                    assert not os.path.exists(partial_path), '.partial must not remain after success'

    def test_raises_value_error_for_unknown_slug(self):
        with pytest.raises(ValueError, match='unknown state slug'):
            download_pbf_if_missing('atlantis')


class TestStateCodeToSlug:
    '''Sanity checks on the STATE_CODE_TO_SLUG mapping.'''

    def test_contains_all_50_states_plus_dc(self):
        '''The mapping should have exactly 51 entries (50 states + DC).'''
        assert len(STATE_CODE_TO_SLUG) == 51

    def test_maps_ga_to_georgia(self):
        assert STATE_CODE_TO_SLUG['GA'] == 'georgia'

    def test_maps_ny_to_new_york_with_hyphen(self):
        '''Multi-word states resolve to hyphenated slugs.'''
        assert STATE_CODE_TO_SLUG['NY'] == 'new-york'

    def test_maps_dc_to_district_of_columbia(self):
        '''DC's slug is fully spelled out and hyphenated.'''
        assert STATE_CODE_TO_SLUG['DC'] == 'district-of-columbia'

    def test_values_are_subset_of_geofabrik_state_slugs(self):
        '''Every slug in the mapping must be a recognized Geofabrik slug.'''
        assert set(STATE_CODE_TO_SLUG.values()) <= GEOFABRIK_STATE_SLUGS

    def test_excludes_unsupported_territories(self):
        '''Territories (PR, GU, AS, MP, VI) live under non-US Geofabrik paths.'''
        for code in ('PR', 'GU', 'AS', 'MP', 'VI'):
            assert code not in STATE_CODE_TO_SLUG


class TestStateSlugFromLocation:
    '''Tests for ``state_slug_from_location``.'''

    def test_single_underscore_location(self):
        assert state_slug_from_location('Gwinnett_GA') == 'georgia'

    def test_multi_underscore_location(self):
        '''Tarrant_County_TX has three underscore-joined segments.'''
        assert state_slug_from_location('Tarrant_County_TX') == 'texas'

    def test_richmond_city_va(self):
        '''Confirm the existing production fixture form parses correctly.'''
        assert state_slug_from_location('Richmond_city_VA') == 'virginia'

    def test_raises_when_no_underscore(self):
        '''A bare token like 'testing' has no parseable state code.'''
        with pytest.raises(ValueError, match='no.*2-letter'):
            state_slug_from_location('testing')

    def test_raises_when_last_segment_is_not_two_chars(self):
        '''Last segment must be exactly two characters to look like a postal code.'''
        with pytest.raises(ValueError, match='no.*2-letter'):
            state_slug_from_location('foo_bar_baz')

    def test_raises_when_last_segment_is_unknown_code(self):
        '''A two-char trailer that isn't a real US postal code.'''
        with pytest.raises(ValueError, match="unknown.*'ZZ'"):
            state_slug_from_location('foo_ZZ')

    def test_raises_when_last_segment_is_lowercase(self):
        '''CLAUDE.md mandates uppercase state codes; lowercase is a typo, not a slug.'''
        with pytest.raises(ValueError, match='no.*2-letter'):
            state_slug_from_location('Gwinnett_ga')


class TestLocationFromConfigFile:
    '''Tests for ``location_from_config_file``.'''

    def test_reads_top_level_location_line(self, tmp_path):
        '''The location: line at column 0 is returned verbatim (trimmed).'''
        cfg = tmp_path / 'cfg.yaml'
        cfg.write_text(
            'config_set: testing\n'
            'config_name: testing_config_driving\n'
            'location: Gwinnett_County_GA\n'
            'census_year: 2020\n'
        )
        assert location_from_config_file(str(cfg)) == 'Gwinnett_County_GA'

    def test_strips_surrounding_single_quotes(self, tmp_path):
        '''YAML permits single-quoted strings; the parser must unwrap them.'''
        cfg = tmp_path / 'cfg.yaml'
        cfg.write_text("location: 'Tarrant_County_TX'\n")
        assert location_from_config_file(str(cfg)) == 'Tarrant_County_TX'

    def test_strips_surrounding_double_quotes(self, tmp_path):
        '''YAML permits double-quoted strings; the parser must unwrap them.'''
        cfg = tmp_path / 'cfg.yaml'
        cfg.write_text('location: "Richmond_city_VA"\n')
        assert location_from_config_file(str(cfg)) == 'Richmond_city_VA'

    def test_ignores_inline_comments(self, tmp_path):
        '''A trailing "# comment" is stripped from the value.'''
        cfg = tmp_path / 'cfg.yaml'
        cfg.write_text('location: Gwinnett_GA  # primary fixture\n')
        assert location_from_config_file(str(cfg)) == 'Gwinnett_GA'

    def test_raises_when_no_location_line(self, tmp_path):
        '''A config missing the location: key must fail clearly.'''
        cfg = tmp_path / 'cfg.yaml'
        cfg.write_text('config_set: testing\ncensus_year: 2020\n')
        with pytest.raises(ValueError, match='no top-level location'):
            location_from_config_file(str(cfg))

    def test_raises_when_file_missing(self, tmp_path):
        '''A missing file is surfaced as ValueError (not bare FileNotFoundError).'''
        with pytest.raises(ValueError, match='could not read config'):
            location_from_config_file(str(tmp_path / 'does-not-exist.yaml'))

    def test_ignores_indented_location_keys(self, tmp_path):
        '''Only column-0 "location:" counts; indented occurrences are nested keys.'''
        cfg = tmp_path / 'cfg.yaml'
        cfg.write_text(
            'config_set: testing\n'
            'something:\n'
            '  location: nested_value\n'
            'location: top_GA\n'
        )
        assert location_from_config_file(str(cfg)) == 'top_GA'
