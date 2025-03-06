'''
SQLAlchemy initial setup

This file contains constumizations and adds funconality to alembic, such
as the ability to create views.
'''
from typing import Type

import os

# from typing import Dict
from sqlalchemy import create_engine
from sqlalchemy.engine.base import Engine
from sqlalchemy.ext.declarative import declarative_base
from alembic.operations import Operations, MigrateOperation

from python import utils

dir_path = os.path.dirname(os.path.realpath(__file__))

DEFAULT_PROJECT = 'equitable-polling-locations'

PRINT_QUERY_DEBUG=False
''' If set to true, SQLAlchemy will print sql queries. '''



ModelBase = declarative_base()

ModelBaseType = Type[ModelBase]

bq_engine: Engine = None


_project = None
_datset = None


def get_db_project() -> str:
    global _project
    if not _project:
        _project = utils.get_env_var_or_prompt('DB_PROJECT', DEFAULT_PROJECT)
    return _project

def get_db_dataset() -> str:
    global _datset
    if not _datset:
        _datset = utils.get_env_var_or_prompt('DB_DATASET')
    return _datset

def get_database_url() -> str:
    return f'bigquery://{get_db_project()}/{get_db_dataset()}'

def setup(): #config: Dict[str,  str]):
    global bq_engine

    database_url = get_database_url()

    if not bq_engine:
        bq_engine = create_engine(url=database_url, echo=PRINT_QUERY_DEBUG)

    return bq_engine

def get_connection():
    # global bq_engine
    if bq_engine:
        return bq_engine.connect()
    return None


class ReversibleOp(MigrateOperation):
    '''
    From: https://alembic.sqlalchemy.org/en/latest/cookbook.html
    Make new operations for create, drop, and replace of views and stored procedures.
    '''
    def __init__(self, target):
        self.target = target

    @classmethod
    def invoke_for_target(cls, operations, target):
        op = cls(target)
        return operations.invoke(op)

    def reverse(self):
        raise NotImplementedError()

    @classmethod
    def _get_object_from_version(cls, operations, ident):
        version, objname = ident.split('.')

        module = operations.get_context().script.get_revision(version).module
        obj = getattr(module, objname)
        return obj

    @classmethod
    def replace(cls, operations, target, replaces=None, replace_with=None):

        if replaces:
            old_obj = cls._get_object_from_version(operations, replaces)
            drop_old = cls(old_obj).reverse()
            create_new = cls(target)
        elif replace_with:
            old_obj = cls._get_object_from_version(operations, replace_with)
            drop_old = cls(target).reverse()
            create_new = cls(old_obj)
        else:
            raise TypeError('replaces or replace_with is required')

        operations.invoke(drop_old)
        operations.invoke(create_new)

# To create usable operations from this base, we will build a series of
# stub classes and use Operations.register_operation() to make them part
# of the op.* namespace:
@Operations.register_operation('create_view', 'invoke_for_target')
@Operations.register_operation('replace_view', 'replace')
class CreateViewOp(ReversibleOp):
    def reverse(self):
        return DropViewOp(self.target)


@Operations.register_operation('drop_view', 'invoke_for_target')
class DropViewOp(ReversibleOp):
    def reverse(self):
        return CreateViewOp(self.target)


@Operations.register_operation('create_sp', 'invoke_for_target')
@Operations.register_operation('replace_sp', 'replace')
class CreateSPOp(ReversibleOp):
    def reverse(self):
        return DropSPOp(self.target)


@Operations.register_operation('drop_sp', 'invoke_for_target')
class DropSPOp(ReversibleOp):
    def reverse(self):
        return CreateSPOp(self.target)


@Operations.implementation_for(CreateViewOp)
def create_view(operations, operation):
    operations.execute('CREATE VIEW %s AS %s' % (
        operation.target.name,
        operation.target.sqltext
    ))


@Operations.implementation_for(DropViewOp)
def drop_view(operations, operation):
    operations.execute('DROP VIEW %s' % operation.target.name)


@Operations.implementation_for(CreateSPOp)
def create_sp(operations, operation):
    operations.execute(
        'CREATE FUNCTION %s %s' % (
            operation.target.name, operation.target.sqltext
        )
    )


@Operations.implementation_for(DropSPOp)
def drop_sp(operations, operation):
    operations.execute('DROP FUNCTION %s' % operation.target.name)

class ReplaceableObject:
    '''
    From: https://alembic.sqlalchemy.org/en/latest/cookbook.html
    A replaceable object is a schema object that needs to be created and dropped all at once.
    Examples of such objects include views, stored procedures, and triggers.
    '''

    def __init__(self, name, sqltext):
        self.name = name
        self.sqltext = sqltext




