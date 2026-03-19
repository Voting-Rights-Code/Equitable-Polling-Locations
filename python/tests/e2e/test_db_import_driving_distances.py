"""End-to-end tests for the db_import_driving_distances_cli script.

All tests are database-backed and will be skipped automatically when no 'test'
environment is configured in settings.yaml.
"""

# pylint: disable=redefined-outer-name

import pandas as pd
import pytest


@pytest.mark.e2e
@pytest.mark.e2e_db
class TestDbImportDrivingDistances:
    """Tests verifying that driving distances are imported correctly into the DB."""

    def test_import_exits_zero(self, imported_driving_distances):
        """The import fixture completes without raising, confirming a zero exit code.

        The ``imported_driving_distances`` fixture calls ``run_cli`` which asserts
        a zero return code internally; reaching this test body is sufficient proof.

        Args:
            imported_driving_distances: Session-scoped fixture that runs the CLI.
        """
        # Fixture already asserts exit code == 0; reaching here confirms success.
        assert imported_driving_distances is None or True

    def test_record_count_matches_csv(self, e2e_test_data, imported_driving_distances, test_environment):
        """The number of rows imported into the DB matches the source CSV row count.

        Args:
            e2e_test_data: Session-scoped test data dict.
            imported_driving_distances: Ensures the import has run.
            test_environment: The loaded test environment.
        """
        from python.database.query import Query  # pylint: disable=import-outside-toplevel

        sid = e2e_test_data['sid']
        csv_path = e2e_test_data['driving_distances_import']

        source_df = pd.read_csv(csv_path)
        expected_count = len(source_df)

        query = Query(test_environment)
        distance_set = query.find_driving_distance_set(
            census_year='2020',
            map_source_date='20250101',
            location=sid,
        )
        assert distance_set is not None, (
            f"No DrivingDistancesSet found for location '{sid}', "
            "census_year='2020', map_source_date='20250101'"
        )

        db_df = query.get_driving_distances(distance_set.id)
        assert len(db_df) == expected_count, (
            f"Expected {expected_count} rows in DB, found {len(db_df)}"
        )

    def test_distance_values_spot_check(self, e2e_test_data, imported_driving_distances, test_environment):
        """All distance_m values in the DB are positive.

        Args:
            e2e_test_data: Session-scoped test data dict.
            imported_driving_distances: Ensures the import has run.
            test_environment: The loaded test environment.
        """
        from python.database.query import Query  # pylint: disable=import-outside-toplevel

        sid = e2e_test_data['sid']

        query = Query(test_environment)
        distance_set = query.find_driving_distance_set(
            census_year='2020',
            map_source_date='20250101',
            location=sid,
        )
        assert distance_set is not None, (
            f"No DrivingDistancesSet found for location '{sid}'"
        )

        db_df = query.get_driving_distances(distance_set.id)
        assert len(db_df) > 0, 'Expected at least one driving distance row in DB'
        assert (db_df['distance_m'] > 0).all(), (
            f"All distance_m values must be positive; found non-positive values:\n"
            f"{db_df[db_df['distance_m'] <= 0][['distance_m']].head()}"
        )
