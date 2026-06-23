"""Unit tests for db_import_distance_data_cli argument parsing."""

import pytest

from python.scripts.db_import_distance_data_cli import build_arg_parser


def test_census_data_type_is_required():
    """Omitting --census_data_type is a parse error (argparse exits non-zero)."""
    parser = build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(['-e', 'test', '2020', 'Test_Location'])


def test_census_data_type_accepts_cvap():
    """--census_data_type CVAP parses and is captured."""
    parser = build_arg_parser()
    args = parser.parse_args(['-e', 'test', '--census_data_type', 'CVAP', '2020', 'Test_Location'])
    assert args.census_data_type == 'CVAP'


def test_census_data_type_rejects_unknown_value():
    """A value outside the choices is a parse error."""
    parser = build_arg_parser()
    with pytest.raises(SystemExit):
        parser.parse_args(['-e', 'test', '--census_data_type', 'ACS', '2020', 'Test_Location'])
