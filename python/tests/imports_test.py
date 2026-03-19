''' Test the database import functions. '''

import os

import numpy as np
import pandas as pd
import pytest
from sqlalchemy import Column, String, Integer, Float
from sqlalchemy.ext.declarative import declarative_base

from python.database import imports, models

_TestBase = declarative_base()


class _NonNullableIntModel(_TestBase):
    ''' Test model with a non-nullable integer column. '''
    __tablename__ = 'test_non_nullable_int'
    id = Column(String(36), primary_key=True)
    name = Column(String(256))
    count = Column(Integer, nullable=False)


class _NonNullableFloatModel(_TestBase):
    ''' Test model with a non-nullable float column. '''
    __tablename__ = 'test_non_nullable_float'
    id = Column(String(36), primary_key=True)
    name = Column(String(256))
    value = Column(Float, nullable=False)


def test_load_model_csv_results(test_results_path):
    ''' Valid results CSV loads with correct shape and types. '''
    df = imports.load_model_csv(models.Result, {}, test_results_path)

    assert len(df) == 4
    assert 'id_orig' in df.columns
    assert 'matching' in df.columns
    assert 'distance_m' in df.columns


def test_load_model_csv_results_column_types(test_results_path):
    ''' Numeric columns are converted to the expected types after loading. '''
    df = imports.load_model_csv(models.Result, {}, test_results_path)

    assert df['population'].dtype == np.int32
    assert df['distance_m'].dtype == np.float64
    assert df['matching'].dtype == np.int32


def test_load_model_csv_results_bad_int(test_results_bad_int_path):
    ''' Float values (1.0) in an integer column are converted to int successfully. '''
    df = imports.load_model_csv(models.Result, {}, test_results_bad_int_path)

    assert df['matching'].dtype == np.int32
    assert (df['matching'] == 1).all()


def test_load_model_csv_residence_distances(test_residence_distances_path):
    ''' Valid residence distances CSV loads with correct shape and types. '''
    df = imports.load_model_csv(models.ResidenceDistance, {}, test_residence_distances_path)

    assert len(df) == 4
    assert 'demographic' in df.columns
    assert df['avg_dist'].dtype == np.float64
    assert df['demo_pop'].dtype == np.int32


def test_load_model_csv_nullable_float_with_null(test_residence_distances_bad_avg_dist_path):
    ''' Null value in a nullable float column loads without error. '''
    df = imports.load_model_csv(
        models.ResidenceDistance, {}, test_residence_distances_bad_avg_dist_path
    )

    assert len(df) == 4
    assert pd.isna(df.loc[1, 'avg_dist'])


def test_load_model_csv_column_renames(test_residence_distances_path):
    ''' Column renames map CSV columns to model columns for type resolution. '''
    column_renames = {'demographic': 'demo_renamed'}
    df = imports.load_model_csv(
        models.ResidenceDistance, column_renames, test_residence_distances_path
    )

    # The original CSV column name should still be present (renames happen later in csv_to_bigquery)
    assert 'demographic' in df.columns


def test_load_model_csv_null_in_non_nullable_int_raises(tmp_path):
    ''' Null in a non-nullable integer column raises ValueError with line info. '''
    csv_path = os.path.join(tmp_path, 'bad_null_int.csv')
    pd.DataFrame({
        'id': ['a', 'b', 'c'],
        'name': ['x', 'y', 'z'],
        'count': [1, None, 3],
    }).to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match=r'Unexpected null value'):
        imports.load_model_csv(_NonNullableIntModel, {}, csv_path)


def test_load_model_csv_null_in_non_nullable_float_raises(tmp_path):
    ''' Null in a non-nullable float column raises ValueError with line info. '''
    csv_path = os.path.join(tmp_path, 'bad_null_float.csv')
    pd.DataFrame({
        'id': ['a', 'b', 'c'],
        'name': ['x', 'y', 'z'],
        'value': [1.0, None, 3.0],
    }).to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match=r'Unexpected null value'):
        imports.load_model_csv(_NonNullableFloatModel, {}, csv_path)


def test_load_model_csv_null_error_reports_line_number(tmp_path):
    ''' ValueError for null in non-nullable column includes the correct CSV line number. '''
    csv_path = os.path.join(tmp_path, 'null_line.csv')
    pd.DataFrame({
        'id': ['a', 'b', 'c'],
        'name': ['x', 'y', 'z'],
        'count': [1, None, 3],
    }).to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match=r'Line: 3'):
        imports.load_model_csv(_NonNullableIntModel, {}, csv_path)


def test_load_model_csv_type_mismatch_raises(tmp_path):
    ''' Non-numeric value in an integer column raises ValueError with detail. '''
    csv_path = os.path.join(tmp_path, 'bad_type.csv')
    pd.DataFrame({
        'id': ['a', 'b', 'c'],
        'name': ['x', 'y', 'z'],
        'count': ['1', 'not_a_number', '3'],
    }).to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match=r'Type mismatch in CSV import'):
        imports.load_model_csv(_NonNullableIntModel, {}, csv_path)


def test_load_model_csv_type_mismatch_reports_column_and_value(tmp_path):
    ''' Type mismatch error includes the column name and failing value. '''
    csv_path = os.path.join(tmp_path, 'bad_value.csv')
    pd.DataFrame({
        'id': ['a', 'b'],
        'name': ['x', 'y'],
        'count': ['1', 'abc'],
    }).to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match=r"(?s)Column: 'count'.*Failed Value: 'abc'"):
        imports.load_model_csv(_NonNullableIntModel, {}, csv_path)
