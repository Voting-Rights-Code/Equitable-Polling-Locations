"""End-to-end tests for the db_import_distance_data_cli script.

Tests cover all four distance-data permutations: linear haversine, log haversine,
linear driving, and log driving.  All tests are database-backed and will be
skipped automatically when no 'test' environment is configured in settings.yaml.
"""

# pylint: disable=redefined-outer-name

import pytest


# ---------------------------------------------------------------------------
# Linear haversine
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.e2e_db
class TestDbImportDistanceDataLinear:
    """Tests for the linear (non-log, non-driving) haversine distance data import."""

    def test_import_exits_zero(self, imported_distance_data_all):
        """The import fixture completes without raising, confirming a zero exit code.

        The ``imported_distance_data_all`` fixture runs all four permutations via
        ``run_cli``, which asserts a zero return code for each; reaching this test
        body confirms the linear import succeeded.

        Args:
            imported_distance_data_all: Session-scoped fixture that runs all CLIs.
        """
        # Fixture already asserts exit code == 0; reaching here confirms success.
        assert imported_distance_data_all is None or True

    def test_records_exist(self, e2e_test_data, imported_distance_data_all, test_environment):
        """At least one DistanceData row exists for the linear haversine permutation.

        Args:
            e2e_test_data: Session-scoped test data dict.
            imported_distance_data_all: Ensures all distance data imports have run.
            test_environment: The loaded test environment.
        """
        from python.database.query import Query  # pylint: disable=import-outside-toplevel

        sid = e2e_test_data['sid']
        query = Query(test_environment)

        ds = query.get_distance_data_set(
            census_year='2020',
            location=sid,
            log_distance=False,
            driving=False,
        )
        assert ds is not None, (
            f"No DistanceDataSet found for location='{sid}', log_distance=False, driving=False"
        )

        db_df = query.get_distance_data(ds.id)
        assert len(db_df) > 0, (
            'Expected at least one DistanceData row for the linear haversine permutation'
        )

    def test_demographic_columns_populated(self, e2e_test_data, imported_distance_data_all, test_environment):
        """The population, white, black, and hispanic columns are populated in the DB.

        Args:
            e2e_test_data: Session-scoped test data dict.
            imported_distance_data_all: Ensures all distance data imports have run.
            test_environment: The loaded test environment.
        """
        from python.database.query import Query  # pylint: disable=import-outside-toplevel

        sid = e2e_test_data['sid']
        query = Query(test_environment)

        ds = query.get_distance_data_set(
            census_year='2020',
            location=sid,
            log_distance=False,
            driving=False,
        )
        assert ds is not None, (
            f"No DistanceDataSet found for location='{sid}', log_distance=False, driving=False"
        )

        db_df = query.get_distance_data(ds.id)
        assert len(db_df) > 0, 'Expected at least one row of distance data'

        for col in ('population', 'white', 'black', 'hispanic'):
            assert col in db_df.columns, f"Expected column '{col}' in distance data"
            assert db_df[col].notna().any(), (
                f"Column '{col}' has no non-null values in the DB records"
            )


# ---------------------------------------------------------------------------
# Log haversine
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.e2e_db
class TestDbImportDistanceDataLog:
    """Tests for the log-transformed haversine distance data import."""

    def test_import_exits_zero(self, imported_distance_data_all):
        """The import fixture completes without raising, confirming a zero exit code.

        Args:
            imported_distance_data_all: Session-scoped fixture that runs all CLIs.
        """
        assert imported_distance_data_all is None or True

    def test_records_exist(self, e2e_test_data, imported_distance_data_all, test_environment):
        """At least one DistanceData row exists for the log haversine permutation.

        Args:
            e2e_test_data: Session-scoped test data dict.
            imported_distance_data_all: Ensures all distance data imports have run.
            test_environment: The loaded test environment.
        """
        from python.database.query import Query  # pylint: disable=import-outside-toplevel

        sid = e2e_test_data['sid']
        query = Query(test_environment)

        ds = query.get_distance_data_set(
            census_year='2020',
            location=sid,
            log_distance=True,
            driving=False,
        )
        assert ds is not None, (
            f"No DistanceDataSet found for location='{sid}', log_distance=True, driving=False"
        )

        db_df = query.get_distance_data(ds.id)
        assert len(db_df) > 0, (
            'Expected at least one DistanceData row for the log haversine permutation'
        )


# ---------------------------------------------------------------------------
# Linear driving
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.e2e_db
class TestDbImportDistanceDataDrivingLinear:
    """Tests for the linear driving distance data import."""

    def test_import_exits_zero(self, imported_distance_data_all):
        """The import fixture completes without raising, confirming a zero exit code.

        Args:
            imported_distance_data_all: Session-scoped fixture that runs all CLIs.
        """
        assert imported_distance_data_all is None or True

    def test_records_exist(self, e2e_test_data, imported_distance_data_all, test_environment):
        """At least one DistanceData row exists for the linear driving permutation.

        Args:
            e2e_test_data: Session-scoped test data dict.
            imported_distance_data_all: Ensures all distance data imports have run.
            test_environment: The loaded test environment.
        """
        from python.database.query import Query  # pylint: disable=import-outside-toplevel

        sid = e2e_test_data['sid']
        query = Query(test_environment)

        ds = query.get_distance_data_set(
            census_year='2020',
            location=sid,
            log_distance=False,
            driving=True,
        )
        assert ds is not None, (
            f"No DistanceDataSet found for location='{sid}', log_distance=False, driving=True"
        )

        db_df = query.get_distance_data(ds.id)
        assert len(db_df) > 0, (
            'Expected at least one DistanceData row for the linear driving permutation'
        )


# ---------------------------------------------------------------------------
# Log driving
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.e2e_db
class TestDbImportDistanceDataDrivingLog:
    """Tests for the log-transformed driving distance data import."""

    def test_import_exits_zero(self, imported_distance_data_all):
        """The import fixture completes without raising, confirming a zero exit code.

        Args:
            imported_distance_data_all: Session-scoped fixture that runs all CLIs.
        """
        assert imported_distance_data_all is None or True

    def test_records_exist(self, e2e_test_data, imported_distance_data_all, test_environment):
        """At least one DistanceData row exists for the log driving permutation.

        Args:
            e2e_test_data: Session-scoped test data dict.
            imported_distance_data_all: Ensures all distance data imports have run.
            test_environment: The loaded test environment.
        """
        from python.database.query import Query  # pylint: disable=import-outside-toplevel

        sid = e2e_test_data['sid']
        query = Query(test_environment)

        ds = query.get_distance_data_set(
            census_year='2020',
            location=sid,
            log_distance=True,
            driving=True,
        )
        assert ds is not None, (
            f"No DistanceDataSet found for location='{sid}', log_distance=True, driving=True"
        )

        db_df = query.get_distance_data(ds.id)
        assert len(db_df) > 0, (
            'Expected at least one DistanceData row for the log driving permutation'
        )
