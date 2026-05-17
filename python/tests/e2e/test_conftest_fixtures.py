"""Tests that verify the e2e conftest fixtures behave correctly.

These tests do not require a DB connection or Docker network access; they only
verify that the session ID has the expected format and that all expected files
are created on disk by the :func:`e2e_test_data` fixture.
"""

import os
import re

import pandas as pd
import pytest
import yaml

from python.tests.e2e.conftest import CONFIG_VARIANTS


@pytest.mark.e2e
@pytest.mark.e2e_csv
class TestE2eSessionId:
    """Verify the session ID fixture produces the correct format."""

    def test_session_id_starts_with_e2e_prefix(self, e2e_session_id):
        """Session ID must start with 'e2e_'."""
        assert e2e_session_id.startswith('e2e_')

    def test_session_id_hex_suffix_is_six_chars(self, e2e_session_id):
        """Session ID must end with exactly 6 lowercase hex characters."""
        suffix = e2e_session_id[len('e2e_'):]
        assert re.fullmatch(r'[0-9a-f]{6}', suffix), (
            f"Expected 6 hex chars after 'e2e_', got: {suffix!r}"
        )

    def test_session_id_total_length(self, e2e_session_id):
        """Session ID must be exactly 10 characters long ('e2e_' + 6)."""
        assert len(e2e_session_id) == 10


@pytest.mark.e2e
@pytest.mark.e2e_csv
class TestE2eTestDataFiles:
    """Verify all expected CSV and YAML files are created by e2e_test_data."""

    def test_polling_dir_exists(self, e2e_test_data):
        """The polling sub-directory must exist."""
        assert os.path.isdir(e2e_test_data['polling_dir'])

    def test_driving_dir_exists(self, e2e_test_data):
        """The driving sub-directory must exist."""
        assert os.path.isdir(e2e_test_data['driving_dir'])

    def test_config_dir_exists(self, e2e_test_data):
        """The config sub-directory must exist."""
        assert os.path.isdir(e2e_test_data['config_dir'])

    def test_potential_locations_csv_exists(self, e2e_test_data):
        """The potential locations CSV must exist."""
        assert os.path.isfile(e2e_test_data['potential_locations'])

    def test_distances_csv_exists(self, e2e_test_data):
        """The linear haversine distances CSV must exist."""
        assert os.path.isfile(e2e_test_data['distances'])

    def test_distances_log_csv_exists(self, e2e_test_data):
        """The log-transformed haversine distances CSV must exist."""
        assert os.path.isfile(e2e_test_data['distances_log'])

    def test_driving_distances_csv_exists(self, e2e_test_data):
        """The driving distances CSV (in polling dir) must exist."""
        assert os.path.isfile(e2e_test_data['driving_distances'])

    def test_driving_distances_log_csv_exists(self, e2e_test_data):
        """The log-transformed driving distances CSV must exist."""
        assert os.path.isfile(e2e_test_data['driving_distances_log'])

    def test_driving_distances_import_csv_exists(self, e2e_test_data):
        """The driving distances CSV for db_import (in driving dir) must exist."""
        assert os.path.isfile(e2e_test_data['driving_distances_import'])

    def test_all_config_variants_exist(self, e2e_test_data):
        """Each of the 8 CONFIG_VARIANTS must have a corresponding YAML file on disk."""
        for suffix in CONFIG_VARIANTS:
            assert suffix in e2e_test_data['configs'], (
                f"Missing key '{suffix}' in e2e_test_data['configs']"
            )
            assert os.path.isfile(e2e_test_data['configs'][suffix]), (
                f"Config file for '{suffix}' not found: {e2e_test_data['configs'][suffix]}"
            )

    def test_autogen_template_exists(self, e2e_test_data):
        """The autogen .yaml_template file must exist."""
        assert os.path.isfile(e2e_test_data['autogen_template'])

    def test_config_variant_count(self, e2e_test_data):
        """Exactly 8 config variants must be created."""
        assert len(e2e_test_data['configs']) == 8


@pytest.mark.e2e
@pytest.mark.e2e_csv
class TestE2eTestDataContent:
    """Verify that the generated files have the expected content."""

    def test_potential_locations_csv_matches_committed_sample(self, e2e_test_data):
        """The potential locations CSV has the row count and columns of the
        committed testing sample at
        ``datasets/polling/testing/testing_potential_locations.csv``.
        """
        df = pd.read_csv(e2e_test_data['potential_locations'])
        assert len(df) == 18, f'Expected 18 rows, got {len(df)}'
        assert list(df.columns) == [
            'Location', 'Address', 'Location type',
            'Latitude', 'Longitude', 'Lat, Lon',
        ], f'Unexpected columns: {list(df.columns)!r}'

    def test_log_distances_have_distance_m_column(self, e2e_test_data):
        """The log-transformed distances CSV must have a 'distance_m' column."""
        df = pd.read_csv(e2e_test_data['distances_log'])
        assert 'distance_m' in df.columns

    def test_log_transform_applied_to_distances(self, e2e_test_data):
        """Log has no fixed points: every row's distance_m differs from the linear source."""
        src_df = pd.read_csv(e2e_test_data['distances'])
        log_df = pd.read_csv(e2e_test_data['distances_log'])
        assert (src_df['distance_m'] != log_df['distance_m']).all()

    def test_driving_distances_differ_from_haversine(self, e2e_test_data):
        """Driving distances must differ from haversine for every matched pair.

        Both fixture CSVs carry the same set of (id_orig, id_dest) pairs but
        in different row orders, so a positional compare would pass for the
        wrong reason. Merge on the pair keys first, then assert inequality on
        the aligned frame.
        """
        haversine_df = pd.read_csv(e2e_test_data['distances'])
        driving_df = pd.read_csv(e2e_test_data['driving_distances'])
        merged = haversine_df[['id_orig', 'id_dest', 'distance_m']].merge(
            driving_df[['id_orig', 'id_dest', 'distance_m']],
            on=['id_orig', 'id_dest'],
            suffixes=('_haversine', '_driving'),
        )
        assert len(merged) > 0, (
            'No matched (id_orig, id_dest) pairs between haversine and driving CSVs'
        )
        assert (merged['distance_m_haversine'] != merged['distance_m_driving']).all(), (
            'Expected every matched pair to have different haversine vs driving '
            'distance_m, but at least one pair matched'
        )

    def test_distance_m_values_are_positive(self, e2e_test_data):
        """The linear distances CSV's distance_m column has no zero or negative values."""
        df = pd.read_csv(e2e_test_data['distances'])
        assert (df['distance_m'] > 0).all()

    def test_config_set_matches_session_id(self, e2e_test_data):
        """Every generated config YAML must have config_set equal to the session ID."""
        sid = e2e_test_data['sid']
        for suffix, config_path in e2e_test_data['configs'].items():
            with open(config_path, 'r', encoding='utf-8') as fh:
                cfg = yaml.safe_load(fh)
            assert cfg['config_set'] == sid, (
                f"config_set mismatch in '{suffix}': expected {sid!r}, got {cfg['config_set']!r}"
            )

    def test_config_location_matches_session_id(self, e2e_test_data):
        """Every generated config YAML must have location equal to the session ID."""
        sid = e2e_test_data['sid']
        for suffix, config_path in e2e_test_data['configs'].items():
            with open(config_path, 'r', encoding='utf-8') as fh:
                cfg = yaml.safe_load(fh)
            assert cfg['location'] == sid, (
                f"location mismatch in '{suffix}': expected {sid!r}, got {cfg['location']!r}"
            )

    def test_config_name_includes_suffix(self, e2e_test_data):
        """Each config's config_name must end with the variant suffix."""
        sid = e2e_test_data['sid']
        for suffix, config_path in e2e_test_data['configs'].items():
            with open(config_path, 'r', encoding='utf-8') as fh:
                cfg = yaml.safe_load(fh)
            assert cfg['config_name'] == f'{sid}_{suffix}', (
                f"config_name mismatch in '{suffix}': got {cfg['config_name']!r}"
            )

    def test_driving_config_has_driving_true(self, e2e_test_data):
        """The 'config_driving' variant must have driving=True."""
        with open(e2e_test_data['configs']['config_driving'], 'r', encoding='utf-8') as fh:
            cfg = yaml.safe_load(fh)
        assert cfg.get('driving') is True

    def test_log_config_has_log_distance_true(self, e2e_test_data):
        """The 'config_log' variant must have log_distance=True."""
        with open(e2e_test_data['configs']['config_log'], 'r', encoding='utf-8') as fh:
            cfg = yaml.safe_load(fh)
        assert cfg.get('log_distance') is True

    def test_penalty_config_has_penalized_sites(self, e2e_test_data):
        """The 'config_penalty' variant must list two penalized sites."""
        with open(e2e_test_data['configs']['config_penalty'], 'r', encoding='utf-8') as fh:
            cfg = yaml.safe_load(fh)
        assert cfg.get('penalized_sites') == [
            'College Campus - Potential',
            'Fire Station - Potential',
        ]

    def test_autogen_template_has_field_to_vary(self, e2e_test_data):
        """The autogen template must specify 'year' as field_to_vary."""
        with open(e2e_test_data['autogen_template'], 'r', encoding='utf-8') as fh:
            tmpl = yaml.safe_load(fh)
        assert tmpl.get('field_to_vary') == 'year'

    def test_autogen_template_has_new_range(self, e2e_test_data):
        """The autogen template new_range must contain 2020 and 2022."""
        with open(e2e_test_data['autogen_template'], 'r', encoding='utf-8') as fh:
            tmpl = yaml.safe_load(fh)
        new_range = tmpl.get('new_range')
        assert new_range == [['2020'], ['2022']]

    def test_driving_distances_import_file_named_correctly(self, e2e_test_data):
        """The driving distances file in driving_dir must follow the naming convention."""
        sid = e2e_test_data['sid']
        expected_name = f'{sid}_driving_distances.csv'
        actual_name = os.path.basename(e2e_test_data['driving_distances_import'])
        assert actual_name == expected_name

    def test_config_dir_is_named_after_session_id(self, e2e_test_data):
        """The config sub-directory must use the session ID as its name."""
        sid = e2e_test_data['sid']
        assert os.path.basename(e2e_test_data['config_dir']) == sid
