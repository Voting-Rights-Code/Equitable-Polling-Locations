'''
DB Convenience methods

Note: these methods are not intended to be thread safe.

Credentials are assumed to be setup by the user by using the glcloud cli.
    e.g. "gcloud auth application-default login"
'''

from dataclasses import fields
from typing import Optional, List
from datetime import datetime
import re

import pandas as pd

from sqlalchemy import desc, func, inspect, select
from sqlalchemy.orm import sessionmaker as SessionMaker

from google.cloud import bigquery

from python.solver.model_config import PollingModelConfig
from python import utils

from . import models
from . import sqlalchemy_main


_session: SessionMaker = None

DB_INTEGER = 'INTEGER'
DB_FLOAT = 'FLOAT'
DB_BOOLEAN = 'BOOLEAN'



def get_session() -> SessionMaker:
    '''
    Returns the existing SQLAlchemy session, if one does not exist then one will be created.
    '''
    global _session
    if not _session:
        engine = sqlalchemy_main.setup()
        _session = SessionMaker(bind=engine)()

    return _session

def find_model_config(config_id: str) -> Optional[models.ModelConfig]:
    ''' Load a config model from the database if it exists, otherwise return None '''
    session = get_session()
    result = session.query(models.ModelConfig).filter(models.ModelConfig.id == config_id).first()

    return result

def find_model_configs_by_config_set(config_set: str) -> List[models.ModelConfig]:
    ''' Returns all of the latest configs by a given config_set. '''
    session = get_session()

    subquery = select(
        models.ModelConfig,
        func.
            row_number().
            over(
                partition_by=[models.ModelConfig.config_set, models.ModelConfig.config_name],
                order_by=desc(models.ModelConfig.created_at)).
            label('rn')
    ).subquery()

    query = select(subquery).where(
        subquery.c.config_set == config_set,
        subquery.c.rn == 1
    ).order_by(subquery.c.config_set, subquery.c.config_name)

    rows = session.execute(query).fetchall()

    results: List[models.ModelConfig] = []
    for row in rows:
        columns = row._asdict()
        del columns['rn']
        results.append(models.ModelConfig(**columns))

    return results

def find_model_configs_by_config_set_and_config_name(config_set: str, config_name: str) -> Optional[models.ModelConfig]:
    ''' Returns the latest config by a given config_set and config_name. '''
    session = get_session()

    subquery = select(
        models.ModelConfig,
        func.
            row_number().
            over(
                partition_by=[models.ModelConfig.config_set, models.ModelConfig.config_name],
                order_by=desc(models.ModelConfig.created_at)).
            label('rn')
    ).subquery()

    query = select(subquery).where(
        subquery.c.config_set == config_set,
        subquery.c.config_name == config_name,
        subquery.c.rn == 1
    )

    row = session.execute(query).fetchone()
    if not row:
        return None

    columns = row._asdict()
    del columns['rn']
    return models.ModelConfig(**columns)


def create_db_model_config(
        config_source: PollingModelConfig,
        config_set_override: str=None,
        config_name_override: str=None,
    ) -> models.ModelConfig:
    ''' Converts a PollingModelConfig config into a DB models.ModelConfig '''


    config_data = {
        'config_set': config_set_override or config_source.config_set,
        'config_name': config_name_override or config_source.config_name,
    }

    for column in models.ModelConfig.__table__.columns:
        column_name = column.name
        if column_name in ['id', 'created_at']:
            continue

        value = getattr(config_source, column_name)
        # print(f'{column_name} -> {value}')

        config_data[column_name] = value

    result = models.ModelConfig(**config_data)

    result.id = result.generate_id()

    return result

def create_polling_model_config(config: models.ModelConfig) -> PollingModelConfig:
    ''' Converts a SQLAlchemy config into the legacy PollingModelConfig dataclass '''

    column_names = [column.name for column in config.__table__.columns]
    column_names.sort()

    model_config_dict = {
        field.name: getattr(config, field.name) for field in fields(PollingModelConfig) if field.name in column_names
    }

    polling_model_config = PollingModelConfig(**model_config_dict)
    polling_model_config.db_id = config.id

    return polling_model_config

def create_model_config(model_config: models.ModelConfig) -> models.ModelConfig:
    '''
    Creates a new ModelConfig object in the database.  Note: query.commit() must be
    called for the object to be commited to the database.
    '''
    model_config.id = model_config.generate_id()

    # print(model_config)

    session = get_session()
    session.add_all([model_config])

    return model_config

def find_or_create_model_config(model_config: models.ModelConfig, log: bool = False) -> models.ModelConfig:
    '''
    Looks for an existing ModelConfig object in the database, if one does not already
    exist then one will be created.  Note: query.commit() must be
    called for the object to be commited to the database.
    '''
    result = find_model_config(model_config.generate_id())
    model_info = f'{model_config.config_set} {model_config.config_name}'

    if not result:
        if log:
            print(f'creating model {model_info}')
        result = create_model_config(model_config)
    else:
        if log:
            print(f'found model {model_info}')
    return result

def create_model_run(
        model_config_id: str,
        polling_locations_set_id: str,
        username: str,
        commit_hash: str,
        created_at: datetime=None,
) -> models.ModelRun:
    '''
    Creates a ModelRun instance in the database. Note: query.commit() must be
    called for the object to be commited to the database.
    '''

    model_run = models.ModelRun(
        id = utils.generate_uuid(),
        model_config_id = model_config_id,
        polling_locations_set_id = polling_locations_set_id,
        username = username,
        commit_hash = commit_hash,
        created_at = created_at,
    )

    session = get_session()
    session.add_all([model_run])

    return model_run


def create_db_distance_set(
    census_year: str,
    map_source_date: str,
    location: str,
) -> models.DrivingDistancesSet:
    result = models.DrivingDistancesSet(
        census_year=census_year,
        map_source_date=map_source_date,
        location=location,
    )

    result.id = utils.generate_uuid()

    session = get_session()
    session.add_all([result])

    return result


def find_driving_distance_set(census_year: str, map_source_date: str, location: str) -> Optional[models.DrivingDistancesSet]:
    session = get_session()

    subquery = select(
        models.DrivingDistancesSet,
        func.
            row_number().
            over(
                partition_by=[
                    models.DrivingDistancesSet.census_year,
                    models.DrivingDistancesSet.map_source_date,
                    models.DrivingDistancesSet.location,
                ],
                order_by=desc(models.DrivingDistancesSet.created_at)).
            label('rn')
    ).subquery()

    query = select(subquery).where(
        subquery.c.census_year == census_year,
        subquery.c.map_source_date == map_source_date,
        subquery.c.location == location,
        subquery.c.rn == 1
    )

    row = session.execute(query).fetchone()

    if not row:
        return None

    columns = row._asdict()
    del columns['rn']
    return models.DrivingDistancesSet(**columns)

def get_driving_distances(driving_distance_set_id: str) -> pd.DataFrame:
    session = get_session()

    table_name = models.DrivingDistance.__tablename__

    query = f'SELECT * FROM {table_name} WHERE driving_distance_set_id = "{driving_distance_set_id}"'

    df = pd.read_sql(query, session.get_bind())
    return df

def find_or_create_driving_distance_set(
    census_year: str,
    map_source_date: str,
    location: str,
    log: bool = False,
) -> models.DrivingDistancesSet:
    '''
    Looks for an existing DistanceSet object in the database, if one does not already
    exist then one will be created.  Note: db.commit() must be
    called for the object to be commited to the database.
    '''
    result = find_driving_distance_set(
        census_year=census_year,
        map_source_date=map_source_date,
        location=location,
    )

    if not result:
        result = create_db_distance_set(
            census_year=census_year,
            map_source_date=map_source_date,
            location=location,
        )
        if log:
            print(f'creating model {result}')
    else:
        if log:
            print(f'found model {result}')
    return result

def create_db_polling_locations_set(
    polling_locations_only_set_id: str,
    census_year: str,
    location: str,
    log_distance: bool,
    driving: bool,
    driving_distance_set_id: str,
) -> models.PollingLocationSet:
    result = models.PollingLocationSet(
        polling_locations_only_set_id=polling_locations_only_set_id,
        census_year=census_year,
        location=location,
        log_distance=log_distance,
        driving=driving,
        driving_distance_set_id=driving_distance_set_id,
    )

    result.id = utils.generate_uuid()

    session = get_session()
    session.add_all([result])

    return result

def create_db_polling_locations_only_set(
    location: str,
) -> models.PollingLocationOnlySet:
    result = models.PollingLocationOnlySet(
        location=location,
    )

    result.id = utils.generate_uuid()

    session = get_session()
    session.add_all([result])

    return result


def get_location_only_set(location: str) -> models.PollingLocationOnlySet:
    session = get_session()

    subquery = select(
        models.PollingLocationOnlySet,
        func.
            row_number().
            over(
                partition_by=[models.PollingLocationOnlySet.location],
                order_by=desc(models.PollingLocationOnlySet.created_at)).
            label('rn')
    ).subquery()

    query = select(subquery).where(
        subquery.c.location == location,
        subquery.c.rn == 1
    )

    row = session.execute(query).fetchone()

    if not row:
        return None

    columns = row._asdict()
    del columns['rn']
    return models.PollingLocationOnlySet(**columns)

def get_locations_only(polling_locations_set_id: str) -> pd.DataFrame:
    session = get_session()

    table_name = models.PollingLocationOnly.__tablename__

    query = f'SELECT * FROM {table_name} WHERE polling_locations_only_set_id = "{polling_locations_set_id}"'

    df = pd.read_sql(query, session.get_bind())
    return df



def get_location_set(census_year: str, location: str, log_distance: bool, driving: bool) -> models.PollingLocationSet:
    session = get_session()

    subquery = select(
        models.PollingLocationSet,
        func.
            row_number().
            over(
                partition_by=[
                    models.PollingLocationSet.census_year,
                    models.PollingLocationSet.location,
                    models.PollingLocationSet.log_distance,
                    models.PollingLocationSet.driving,
                ],
                order_by=desc(models.PollingLocationSet.created_at)).
            label('rn')
    ).subquery()

    query = select(subquery).where(
        subquery.c.census_year == census_year,
        subquery.c.location == location,
        subquery.c.log_distance == log_distance,
        subquery.c.driving == driving,
        subquery.c.rn == 1
    )

    row = session.execute(query).fetchone()

    if not row:
        return None

    columns = row._asdict()
    del columns['rn']
    return models.PollingLocationSet(**columns)

def get_locations(polling_locations_set_id: str) -> pd.DataFrame:
    session = get_session()

    table_name = models.PollingLocation.__tablename__

    # pylint: disable-next=line-too-long
    query = f'SELECT * FROM {table_name} WHERE polling_locations_set_id = "{polling_locations_set_id}"'

    df = pd.read_sql(query, session.get_bind())
    return df


def bigquery_client() -> bigquery.Client:
    ''' Returns an instance of bigquery.Client, handling all needed credentials. '''
    return bigquery.Client(project=sqlalchemy_main.get_db_project())

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

def commit():
    '''
    Commits the current SQLAlchemy session and sets the current one to None. If query.get_session()
    is called after this function then a new session will be created.
    '''
    global _session
    session = _session
    _session = None
    session.commit()
