"""End-to-end tests for the db_import_distance_data_cli script.

Tests cover all four distance-data permutations: linear haversine, log haversine,
linear driving, and log driving.  All tests are database-backed and will be
skipped automatically when no 'test' environment is configured in settings.yaml.
"""

# pylint: disable=redefined-outer-name

import pytest

# Source CSVs (testing_distances_2020.csv and testing_driving_2020.csv) each
# have 200 data rows; log variants are derived row-for-row from the linear
# sources, so all four permutations import the same row count.
EXPECTED_ROW_COUNT = 200


@pytest.mark.e2e
@pytest.mark.e2e_db
@pytest.mark.usefixtures('imported_distance_data_all')
class TestDbImportDistanceData:
    """Tests for the four distance-data CLI import permutations.

    The ``imported_distance_data_all`` fixture is wired via ``usefixtures`` so
    every test in this class triggers the four CLI imports without taking the
    fixture as an unused parameter.  Each ``test_<permutation>`` method calls
    :meth:`_verify_imported_set` with the (log_distance, driving) flags for one
    permutation; the helper checks both the row count and the full ORM column
    set against the loaded DataFrame.
    """

    @staticmethod
    def _verify_imported_set(
        e2e_test_data, test_environment, *, log_distance: bool, driving: bool,
    ) -> None:
        """Verify row count and column set for one (log_distance, driving) permutation.

        Args:
            e2e_test_data: Session-scoped test data dict.
            test_environment: The loaded test environment.
            log_distance: Whether this permutation log-transformed distance_m.
            driving: Whether this permutation used driving distances.
        """
        from python.database.models import DistanceData  # pylint: disable=import-outside-toplevel
        from python.database.query import Query  # pylint: disable=import-outside-toplevel

        sid = e2e_test_data['sid']
        query = Query(test_environment)

        ds = query.get_distance_data_set(
            census_year='2020',
            census_data_type='redistricting',
            location=sid,
            log_distance=log_distance,
            driving=driving,
        )
        assert ds is not None, (
            f"No DistanceDataSet found for location='{sid}', "
            f'log_distance={log_distance}, driving={driving}'
        )

        db_df = query.get_distance_data(ds.id)

        assert len(db_df) == EXPECTED_ROW_COUNT, (
            f'Expected {EXPECTED_ROW_COUNT} DistanceData rows for '
            f'log_distance={log_distance}, driving={driving}, got {len(db_df)}'
        )

        expected_cols = {col.name for col in DistanceData.__table__.columns}
        actual_cols = set(db_df.columns)
        assert actual_cols == expected_cols, (
            f'Column mismatch for log_distance={log_distance}, driving={driving}: '
            f'missing={expected_cols - actual_cols!r}, '
            f'unexpected={actual_cols - expected_cols!r}'
        )

        assert (db_df['distance_m'] > 0).all(), (
            f'All distance_m values must be positive for log_distance={log_distance}, '
            f'driving={driving}; found non-positive values:\n'
            f"{db_df[db_df['distance_m'] <= 0][['id_orig', 'id_dest', 'distance_m']].head()!r}"
        )

    def test_linear_haversine(self, e2e_test_data, test_environment):
        """Linear haversine: log_distance=False, driving=False."""
        self._verify_imported_set(
            e2e_test_data, test_environment,
            log_distance=False, driving=False,
        )

    def test_log_haversine(self, e2e_test_data, test_environment):
        """Log-transformed haversine: log_distance=True, driving=False."""
        self._verify_imported_set(
            e2e_test_data, test_environment,
            log_distance=True, driving=False,
        )

    def test_linear_driving(self, e2e_test_data, test_environment):
        """Linear driving: log_distance=False, driving=True."""
        self._verify_imported_set(
            e2e_test_data, test_environment,
            log_distance=False, driving=True,
        )

    def test_log_driving(self, e2e_test_data, test_environment):
        """Log-transformed driving: log_distance=True, driving=True."""
        self._verify_imported_set(
            e2e_test_data, test_environment,
            log_distance=True, driving=True,
        )
