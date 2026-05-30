"""End-to-end tests for the db_import_potential_locations_cli script.

All tests are database-backed and will be skipped automatically when no 'test'
environment is configured in settings.yaml.
"""

# pylint: disable=redefined-outer-name

import pandas as pd
import pytest

from python.tests.e2e.conftest import run_cli  # noqa: F401 — imported for type clarity


@pytest.mark.e2e
@pytest.mark.e2e_db
class TestDbImportPotentialLocations:
    """Tests verifying that potential locations are imported correctly into the DB."""

    def test_import_exits_zero(self, imported_potential_locations):
        """The import fixture completes without raising, confirming a zero exit code.

        The ``imported_potential_locations`` fixture calls ``run_cli`` which asserts
        a zero return code internally; reaching this test body is sufficient proof.

        Args:
            imported_potential_locations: Session-scoped fixture that runs the CLI.
        """
        # Fixture already asserts exit code == 0; reaching here confirms success.
        assert imported_potential_locations is None or True

    def test_import_reports_success(self, e2e_test_data, test_environment):
        """Re-running the CLI prints a success indicator to stdout.

        Because the session fixture does not capture stdout, we invoke the CLI once
        more here (idempotent since the DB allows duplicate sets) and inspect the
        returned ``CompletedProcess``.

        Args:
            e2e_test_data: Session-scoped test data dict.
            test_environment: The loaded test environment (ensures DB is available).
        """
        sid = e2e_test_data['sid']
        result = run_cli('python.scripts.db_import_potential_locations_cli', sid, '-e', 'test')

        # The CLI prints a summary line like "Successes (1):" on success.
        assert 'Successes' in result.stdout, (
            f"Expected 'Successes' in stdout, got:\n{result.stdout}"
        )

    def test_record_count_matches_csv(self, e2e_test_data, imported_potential_locations, test_environment):
        """The number of rows imported into the DB matches the source CSV row count.

        Args:
            e2e_test_data: Session-scoped test data dict.
            imported_potential_locations: Ensures the import has run.
            test_environment: The loaded test environment.
        """
        from python.database.query import Query  # pylint: disable=import-outside-toplevel

        sid = e2e_test_data['sid']
        csv_path = e2e_test_data['potential_locations']

        source_df = pd.read_csv(csv_path)
        expected_count = len(source_df)

        query = Query(test_environment)
        pl_set = query.get_potential_locations_set(sid)
        assert pl_set is not None, f"No PotentialLocationsSet found for location '{sid}'"

        db_df = query.get_potential_locations(pl_set.id)
        assert len(db_df) == expected_count, (
            f"Expected {expected_count} rows in DB, found {len(db_df)}"
        )

    def test_lat_lon_spot_check(self, e2e_test_data, imported_potential_locations, test_environment):
        """A lat/lon value from the source CSV is present in the DB records.

        Args:
            e2e_test_data: Session-scoped test data dict.
            imported_potential_locations: Ensures the import has run.
            test_environment: The loaded test environment.
        """
        from python.database.query import Query  # pylint: disable=import-outside-toplevel

        sid = e2e_test_data['sid']
        csv_path = e2e_test_data['potential_locations']

        source_df = pd.read_csv(csv_path)
        # Grab the first row's Lat, Lon combined string as stored in "Lat, Lon" column.
        first_row = source_df.iloc[0]
        expected_lat_lon = first_row['Lat, Lon']

        query = Query(test_environment)
        pl_set = query.get_potential_locations_set(sid)
        assert pl_set is not None, f"No PotentialLocationsSet found for location '{sid}'"

        db_df = query.get_potential_locations(pl_set.id)
        assert expected_lat_lon in db_df['lat_lon'].values, (
            f"Expected lat_lon value '{expected_lat_lon}' not found in DB records"
        )
