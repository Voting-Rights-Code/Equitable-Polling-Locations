''' Utilities to import csv files into the database.'''

import os
import re

from dataclasses import dataclass
from typing import Dict, Optional, List

import numpy as np
import pandas as pd
import sqlalchemy
from sqlalchemy import inspect

from python.solver.model_config import PollingModelConfig
from python.utils.environments import Environment
from python import utils

from . import models
from . import query
from . import sqlalchemy_main

DB_INTEGER = 'INTEGER'
DB_FLOAT = 'FLOAT'
DB_BOOLEAN = 'BOOLEAN'

@dataclass
class ImportResult:
    ''' A simple class to report results on imports and if there were any problems '''
    config_set: str
    config_name: str
    table_name: str
    success: bool
    source_file: str
    rows_written: int
    exception: Optional[Exception]
    timestamp: str = None

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = utils.current_time_utc()


def bigquery_bluk_insert_dataframe(environment: Environment, table_name, df: pd.DataFrame, log: bool = False) -> int:
    '''
    Uploads a dataframe into a bigquery table in bulk using the bigquery client library.
    This function does not use sessions.
    '''
    client = query.bigquery_client(environment)
    destination = f'{environment.dataset}.{table_name}'

    job = client.load_table_from_dataframe(
        df,
        destination
    )

    job.result()
    if log:
        print(f'Wrote {job.output_rows} rows to table {destination}')
    return job.output_rows




def build_model_column_types(model_class: sqlalchemy_main.ModelBaseType) -> Dict[str, str]:
    '''
    Builds a dictionary of column names and their types for the given model class.
    This is used to set the dtypes for reading in the csv file.
    '''

    column_types = {}
    inspector = inspect(model_class)
    for column in inspector.columns:
        if isinstance(column.type, sqlalchemy.String):
            column_types[column.name] = str
        elif isinstance(column.type, sqlalchemy.Integer):
            column_types[column.name] = np.int32
        elif isinstance(column.type, sqlalchemy.Float):
            column_types[column.name] = np.float64
        elif isinstance(column.type, sqlalchemy.DateTime):
            column_types[column.name] = str
        else:
            column_types[column.name] = str

    return column_types


def load_model_csv(
    model_class: sqlalchemy_main.ModelBaseType,
    column_renames: Dict[str, str],
    csv_path: str,
) -> pd.DataFrame:
    '''
    Loads a csv file into a pandas dataframe and sets the dtypes based on the model class.
    This is used to set the dtypes for reading in the csv file.
    '''
    model_column_types = build_model_column_types(model_class)
    reversed_column_renames = {value: key for key, value in column_renames.items()}

    # Read the header of the csv file to get the column names
    df_header = pd.read_csv(csv_path, nrows=0)
    csv_header_list = df_header.columns.tolist()

    # print('load_model_csv', csv_path)

    converters = {}

    for csv_column in csv_header_list:
        model_column = reversed_column_renames.get(csv_column) or csv_column

        column_type = model_column_types.get(model_column)

        if column_type is not None:
            # print(f'  Column {csv_column} is of type {column_type}')
            # Prevent pandas from converting empty strings to NaN
            if column_type == np.float64:
                converters[csv_column] = utils.csv_float_converter
            elif column_type == np.int32:
                converters[csv_column] = utils.csv_int_converter
            else:
                converters[csv_column] = utils.csv_str_converter


    df = pd.read_csv(
        csv_path,
        low_memory=False,
        na_filter=True,
        keep_default_na=True,
        converters=converters,
    )

    # print(df.head())

    return df

def set_column_types(df: pd.DataFrame, model_class: sqlalchemy) -> pd.DataFrame:
    '''
    Sets the dtypes for the given dataframe based on the model class.
    This is used to set the dtypes for reading in the csv file.
    '''

    inspector = inspect(model_class)
    string_columns = [
        column.name
        for column in inspector.columns
        if isinstance(column.type, sqlalchemy.String) and column.name in df.columns
    ]

    double_columns = [
        column.name
        for column in inspector.columns
        if isinstance(column.type, sqlalchemy.Double) and column.name in df.columns
    ]

    float_columns = [
        column.name
        for column in inspector.columns
        if isinstance(column.type, sqlalchemy.Float) and column.name in df.columns
    ]

    # Force convert all df columns types to match what is expected in the SQLAlchemy model
    # This is important since columns such as orig_id that get loaded as an int by pd.read_csv.
    df[string_columns] = df[string_columns].astype(str)
    df[double_columns] = df[double_columns].astype(float)
    df[float_columns] = df[float_columns].astype(float)

    return df

def csv_to_bigquery(
    environment: Environment,
    config_set: str,
    config_name: str,
    model_class: sqlalchemy_main.ModelBaseType,
    ignore_columns: List[str],
    column_renames: Dict[str, str],
    add_columns: Dict[str, str],
    csv_path: str = None,
    df: pd.DataFrame = None,
    log: bool = False,
):
    '''
    Loads in a csv file or DataFrame, alterns columns as needed, and builk uploads the values to bigquery.
    Note: this is done as a bulk upload since SQLAlchemy inserts are not performant enough to do it via
    models or raw queries.
    '''

    # Build a dictionary of column renames to reverse the column renames
    # This is used to set types for csv reading

    try:
        table_name = model_class.__tablename__

        # IF a dataframe is not already provided, load from the csv_path param
        if df is None:
            # We are intentionally not using the pd.read_csv dtype here since we want to use our
            # own validations to generate more info instead of depending on pandas ability to cast
            # from float to int, etc.
            df = load_model_csv(model_class, column_renames, csv_path)
        else:
            csv_path = '[From DataFrame]'

        source_column_names = df.columns.tolist()

        # Delete columns as needed to match the model
        for source_column_name in source_column_names:
            if source_column_name in ignore_columns:
                del df[source_column_name]

        if column_renames:
            df = df.rename(columns=column_renames)

        df = set_column_types(df, model_class)

        # Add any additional columns needed from the add_columns paramater
        for new_column, value in add_columns.items():
            df[new_column] = value

        # Delete any unamed columns
        mask = ~df.columns.astype(str).str.startswith('Unnamed', na=False)
        df = df.loc[:, mask]

        if log:
            print(f'--\nImporting into table `{table_name}` from {csv_path}')

        # Throw an error if there are any values in the df that do not meet expected types
        validate_csv_columns(model_class, df)

        # Upload the data to bigquery in builk
        rows_written = bigquery_bluk_insert_dataframe(environment, table_name, df)

        return ImportResult(
            config_set=config_set,
            config_name=config_name,
            table_name=table_name,
            success=True,
            source_file=csv_path,
            rows_written=rows_written,
            exception=None,
        )
    # pylint: disable-next=broad-exception-caught
    except Exception as e:
        result = ImportResult(
            config_set=config_set,
            config_name=config_name,
            table_name=table_name,
            success=False,
            source_file=csv_path,
            rows_written=0,
            exception=e,
        )
        print(f'Import failed:\n{e}')
        return result

def import_edes(
    environment: Environment,
    config_set: str,
    config_name: str,
    model_run_id: str,
    csv_path: str = None,
    df: pd.DataFrame = None,
    log: bool = False,
) -> ImportResult:
    ''' Imports an existing EDEs csv into the database for a given mode_run_id. '''

    column_renames = {}
    ignore_columns = ['V1']
    add_columns = { 'model_run_id': model_run_id }

    return csv_to_bigquery(
        environment=environment,
        config_set=config_set,
        config_name=config_name,
        model_class=models.EDES,
        ignore_columns=ignore_columns,
        column_renames=column_renames,
        add_columns=add_columns,
        csv_path=csv_path,
        df=df,
        log=log,
    )

def import_precinct_distances(
    environment: Environment,
    config_set: str,
    config_name: str,
    model_run_id: str,
    csv_path: str = None,
    df: pd.DataFrame = None,
    log: bool = False,
) -> ImportResult:
    ''' Imports an existing precinct distances csv into the database for a given mode_run_id. '''

    column_renames = {}
    ignore_columns = ['V1']
    add_columns = { 'model_run_id': model_run_id }

    return csv_to_bigquery(
        environment=environment,
        config_set=config_set,
        config_name=config_name,
        model_class=models.PrecintDistance,
        ignore_columns=ignore_columns,
        column_renames=column_renames,
        add_columns=add_columns,
        csv_path=csv_path,
        df=df,
        log=log,
    )

def import_residence_distances(
    environment: Environment,
    config_set: str,
    config_name: str,
    model_run_id: str,
    csv_path: str = None,
    df: pd.DataFrame = None,
    log: bool = False,
) -> ImportResult:
    ''' Imports an existing residence distances csv into the database for a given mode_run_id. '''

    column_renames = {}
    ignore_columns = ['V1']
    add_columns = { 'model_run_id': model_run_id }

    return csv_to_bigquery(
        environment=environment,
        config_set=config_set,
        config_name=config_name,
        model_class=models.ResidenceDistance,
        ignore_columns=ignore_columns,
        column_renames=column_renames,
        add_columns=add_columns,
        csv_path=csv_path,
        df=df,
        log=log,
    )

def import_results(
    environment: Environment,
    config_set: str,
    config_name: str,
    model_run_id: str,
    csv_path: str = None,
    df: pd.DataFrame = None,
    log: bool = False,
) -> ImportResult:
    ''' Imports an existing precinct distances csv into the database for a given mode_run_id. '''

    column_renames = {
        #'non-hispanic': 'non_hispanic',
        #'Weighted_dist': 'weighted_dist',
        #'KP_factor': 'kp_factor',
    }
    ignore_columns = ['V1']
    add_columns = { 'model_run_id': model_run_id }
    if df is not None: #if csv path given, then df should be null. when reading from csv, there is no index.
        df.reset_index(drop=True, inplace=True)

    return csv_to_bigquery(
        environment=environment,
        config_set=config_set,
        config_name=config_name,
        model_class=models.Result,
        ignore_columns=ignore_columns,
        column_renames=column_renames,
        add_columns=add_columns,
        csv_path=csv_path,
        df=df,
        log=log,
    )


def print_all_import_results(import_results_list: List[ImportResult], output_path: str=None):
    ''' Prints to the screen a summary of all import results. '''

    data = {
        'timestamp': [ r.timestamp for r in import_results_list ],
        'config_set': [ r.config_set for r in import_results_list ],
        'config_name': [ r.config_name for r in import_results_list ],
        'success': [ r.success for  r in import_results_list ],
        'table_name': [ r.table_name for r in import_results_list ],
        'source_file': [ r.source_file for r in import_results_list ],
        'rows_written': [ r.rows_written for  r in import_results_list ],
        'error': [ str(r.exception or '') for  r in import_results_list ],
    }

    df = pd.DataFrame(data)
    if output_path:
        # Write to a file

        if os.path.exists(output_path):
            mode = 'a'
            header = False
        else:
            mode = 'w'
            header = True
        df.to_csv(output_path, mode=mode, header=header, index=False)
    else:
        # Write to the screen
        print(df.to_csv(index=False))


def validate_csv_columns(model_class: sqlalchemy_main.ModelBaseType, df: pd.DataFrame, log: bool = False):
    '''
    Raises an error if the value loaded from the df does not match what is expected in the model
    schema.
    '''
    inspector = inspect(model_class)
    column_type_map: dict[str, str] = {}
    for column in inspector.columns:
        column_type_map[column.name] = str(column.type)

    if log:
        print(f'validate_csv_columns df:\n{df}')
    # 1-index and adjust for header
    row_num = 2
    for _, row in df.iterrows():
        # The row number of the source csv file
        row_num += 1

        for expected_name, expected_type in column_type_map.items():
            if expected_name == 'id':
                continue
            val = row.get(expected_name)
            # print(f'row_num: {row_num}, val: {val}, expected_type: {expected_type}')
            if val is None or (val is pd.NA):
                continue

            if str(expected_type) == DB_FLOAT:
                if val and not utils.is_float(val):
                    raise ValueError(
                        # pylint: disable-next=line-too-long
                        f'Unexpected column `{expected_name}` type {expected_type} with value of "{val}" on row num {row_num}'
                    )
            elif expected_type == DB_INTEGER:
                if val and not utils.is_int(val):
                    raise ValueError(
                        # pylint: disable-next=line-too-long
                        f'Unexpected column `{expected_name}` type {expected_type} with value of "{val}" on row num {row_num}'
                    )
            elif re.match(r'^VARCHAR.*', str(expected_type)):
                if val and not utils.is_str(val):
                    raise ValueError(
                        # pylint: disable-next=line-too-long
                        f'Unexpected column `{expected_name}` type {expected_type} with value of "{val}" on row num {row_num}'
                    )
            elif str(expected_type) == DB_BOOLEAN:
                if not utils.is_boolean(val):
                    raise ValueError(
                        # pylint: disable-next=line-too-long
                        f'Unexpected column `{expected_name}` type {expected_type} with value of "{val}" on row num {row_num}'
                    )
            else:
                raise ValueError(
                    # pylint: disable-next=line-too-long
                    f'Unknown value type for column `{expected_name}` type {expected_type} with value of "{val}" on row num {row_num}'
                )
