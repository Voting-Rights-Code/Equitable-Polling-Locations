''' Utilities to import csv files into the database.'''

import os

from dataclasses import dataclass
from python import utils
from typing import Dict, Optional, List

import pandas as pd
import sqlalchemy
from sqlalchemy import inspect

from . import models
from . import query
from . import sqlalchemy_main

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

def bigquery_bluk_insert_dataframe(table_name, df: pd.DataFrame, log: bool = False) -> int:
    '''
    Uploads a dataframe into a bigquery table in bulk using the bigquery client library.
    '''
    client = query.bigquery_client()
    destination = f'{sqlalchemy_main.get_db_dataset()}.{table_name}'

    job = client.load_table_from_dataframe(
        df,
        destination
    )

    job.result()
    if log:
        print(f'Wrote {job.output_rows} rows to table {destination}')
    return job.output_rows


def csv_to_bigquery(
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

    try:
        table_name = model_class.__tablename__


        # IF a dataframe is not already provided, load from the csv_path param
        if df is None:
            # We are intentionally not using the pd.read_csv dtype here since we want to use our
            # own validations to generate more info instead of depending on pandas ability to cast
            # from float to int, etc.
            df = pd.read_csv(csv_path) #, na_filter=False, keep_default_na=False)
        else:
            csv_path = '[From DataFrame]'

        source_column_names = df.columns.tolist()

        # Delete columns as needed to match the model
        for source_column_name in source_column_names:
            if source_column_name in ignore_columns:
                del df[source_column_name]

        if column_renames:
            df = df.rename(columns=column_renames)

        # Force convert all df columns to string type if they are a type string the SQLAlchemy model
        # This is important since columns such as orig_id that get loaded as an int by pd.read_csv.
        inspector = inspect(model_class)
        string_columns = [
            column.name
            for column in inspector.columns
            if isinstance(column.type, sqlalchemy.String) and column.name in df.columns
        ]
        df[string_columns] = df[string_columns].astype(str)

        double_columns = [
            column.name
            for column in inspector.columns
            if isinstance(column.type, sqlalchemy.Double) and column.name in df.columns
        ]
        df[double_columns] = df[double_columns].astype(float)

        float_columns = [
            column.name
            for column in inspector.columns
            if isinstance(column.type, sqlalchemy.Float) and column.name in df.columns
        ]
        df[float_columns] = df[float_columns].astype(float)

        # Add any additional columns needed from the add_columns paramater
        for new_column, value in add_columns.items():
            df[new_column] = value

        # Delete any unamed columns
        mask = ~df.columns.astype(str).str.startswith('Unnamed', na=False)
        df = df.loc[:, mask]

        if log:
            print(f'--\nImporting into table `{table_name}` from {csv_path}')

        # Throw an error if there are any values in the df that do not meet expected types
        query.validate_csv_columns(model_class, df)

        # Upload the data to bigquery in builk
        rows_written = bigquery_bluk_insert_dataframe(table_name, df)

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
        config_set: str,
        config_name: str,
        model_run_id: str,
        csv_path: str = None,
        df: pd.DataFrame = None,
        log: bool = False,
) -> ImportResult:
    ''' Imports an existing precinct distances csv into the database for a given mode_run_id. '''

    column_renames = {
        'non-hispanic': 'non_hispanic',
        'Weighted_dist': 'weighted_dist',
        'KP_factor': 'kp_factor',
    }
    ignore_columns = ['V1']
    add_columns = { 'model_run_id': model_run_id }
    if df is not None: #if csv path given, then df should be null. when reading from csv, there is no index.
        df.reset_index(drop=True, inplace=True)

    return csv_to_bigquery(
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
