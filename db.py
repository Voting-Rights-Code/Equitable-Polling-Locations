'''
DB Convenience methods

Note: these methods are not intended to be thread safe.

Credentials are assumed to be setup by the user by using the glcloud cli.
    e.g. "gcloud auth application-default login"
'''

from dataclasses import dataclass
from typing import Dict, Optional, List
from datetime import datetime
import re

import pandas as pd

import sqlalchemy
from sqlalchemy import inspect
from sqlalchemy.orm import sessionmaker as SessionMaker

import sqlalchemy_main
import models as Models
from utils import generate_uuid

from google.cloud import bigquery

import utils

_session: SessionMaker = None

DB_INTEGER = 'INTEGER'
DB_FLOAT = 'FLOAT'

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

def get_session() -> SessionMaker:
    '''
    Returns the existing SQLAlchemy session, if one does not exist then one will be created.
    '''
    global _session
    if not _session:
        engine = sqlalchemy_main.setup()
        _session = SessionMaker(bind=engine)()

    return _session

def find_model_config(config_id: str) -> Optional[Models.ModelConfig]:
    ''' Load a config model from the database if it exists, otherwise return None '''
    session = get_session()
    result = session.query(Models.ModelConfig).filter(Models.ModelConfig.id == config_id).first()

    return result

def create_model_config(model_config: Models.ModelConfig) -> Models.ModelConfig:
    '''
    Creates a new ModelConfig object in the database.  Note: db.commit() must be
    called for the object to be commited to the database.
    '''
    model_config.id = model_config.generate_id()

    # print(model_config)

    session = get_session()
    session.add_all([model_config])

    return model_config

def find_or_create_model_config(model_config: Models.ModelConfig) -> Models.ModelConfig:
    '''
    Looks for an existing ModelConfig object in the database, if one does not already
    exist then one will be created.  Note: db.commit() must be
    called for the object to be commited to the database.
    '''
    result = find_model_config(model_config.generate_id())
    model_info = f'{model_config.config_set} {model_config.config_name}'

    if not result:
        print(f'creating model {model_info}')
        result = create_model_config(model_config)
    else:
        print(f'found model {model_info}')
    return result

def create_model_run(
        model_config_id: str,
        username: str,
        commit_hash: str,
        created_at: datetime=None,
) -> Models.ModelRun:
    '''
    Creates a ModelRun instance in the database. Note: db.commit() must be
    called for the object to be commited to the database.
    '''

    model_run = Models.ModelRun(
        id = generate_uuid(),
        model_config_id = model_config_id,
        username = username,
        commit_hash = commit_hash,
        created_at = created_at,
    )

    session = get_session()
    session.add_all([model_run])

    return model_run

def bigquery_client() -> bigquery.Client:
    ''' Returns an instance of bigquery.Client, handling all needed credentials. '''
    return bigquery.Client(project=sqlalchemy_main.PROJECT)


def bigquery_bluk_insert_dataframe(table_name, df: pd.DataFrame) -> int:
    '''
    Uploads a dataframe into a bigquery table in bulk using the bigquery client library.
    '''
    client = bigquery_client()
    destination = f'{sqlalchemy_main.DATASET}.{table_name}'

    job = client.load_table_from_dataframe(
        df,
        destination
    )

    job.result()
    print(f'Wrote {job.output_rows} rows to table {destination}')
    return job.output_rows


def validate_csv_columns(model_class: sqlalchemy_main.ModelBaseType, df: pd.DataFrame):
    '''
    Raises an error if the value loaded from the df does not match what is expected in the model
    schema.
    '''
    inspector = inspect(model_class)
    column_type_map: dict[str, str] = {}
    for column in inspector.columns:
        column_type_map[column.name] = str(column.type)

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
            else:
                raise ValueError(
                    # pylint: disable-next=line-too-long
                    f'Unknown value type for column `{expected_name}` type {expected_type} with value of "{val}" on row num {row_num}'
                )

def csv_to_bigquery(
        config_set: str,
        config_name: str,
        model_class: sqlalchemy_main.ModelBaseType,
        ignore_columns: List[str],
        column_renames: Dict[str, str],
        add_columns: Dict[str, str],
        csv_path: str = None,
        df: pd.DataFrame = None,

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

        # Add any additional columns needed from the add_columns paramater
        for new_column, value in add_columns.items():
            df[new_column] = value

        print(f'--\nImporting into table `{table_name}` from {csv_path}')

        # Throw an error if there are any values in the df that do not meet expected types
        validate_csv_columns(model_class, df)

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
        result =  ImportResult(
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


def commit():
    '''
    Commits the current SQLAlchemy session and sets the current one to None. If db.get_session()
    is called after this function then a new session will be created.
    '''
    global _session
    session = _session
    _session = None
    session.commit()
