'''
    models/user.py
'''
from typing import List
import hashlib
import json

from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, ForeignKey, text, ARRAY
from sqlalchemy.orm import mapped_column, Mapped, relationship

from sqlalchemy_main import ModelBase
from utils import current_time_utc, generate_uuid

class ModelConfig(ModelBase):
    ''' Model Configuration SQLAlchemy record  '''

    __tablename__ = 'model_configs'

    id: Mapped[str] = mapped_column(String(40), primary_key=True, nullable=False)
    ''' primary key of the model config that is made up of a hash of all columns excluding dates'''

    config_set: str = Column(String(256), nullable=False)
    ''' The name of the set of configs that this config belongs to. '''

    config_name: str = Column(String(256), nullable=False)
    ''' The name of this model config. '''

    location: str = Column(String(256))
    ''' Location for this model. '''

    year: List[str] = Column(ARRAY(String(256), as_tuple=False, dimensions=None, zero_indexes=False))
    ''' An array of years for this model. '''

    bad_types: List[str] = Column(ARRAY(String(256), as_tuple=False, dimensions=None, zero_indexes=False))
    ''' A list of location types not to be considered in this model'''

    beta: float = Column(Float)
    '''
    level of inequality aversion: [-10,0], where 0 indicates indifference, and thus uses the
    mean. -2 isa good number.
    '''

    time_limit: float = Column(Float)
    '''How long the solver should try to find a solution'''

    penalized_sites: List[str] = Column(ARRAY(String(256), as_tuple=False, dimensions=None, zero_indexes=False))
    '''
    A list of locations for which the preference is to only place a polling location there
    if absolutely necessary for coverage, e.g. fire stations.
    '''

    precincts_open: int = Column(Integer)
    '''The total number of precincts to be used this year. If no
    user input is given, this is calculated to be the number of
    polling places identified in the data.'''

    maxpctnew: float = Column(Float)
    '''The percent on new polling places (not already defined as a
    polling location) permitted in the data. Default = 1. I.e. can replace all existing locations'''

    minpctold: float = Column(Float)
    '''The minimun number of polling places (those already defined as a
    polling location) permitted in the data. Default = 0. I.e. can replace all existing locations'''

    max_min_mult: float = Column(Float)
    '''A multiplicative factor for the min_max distance caluclated
    from the data. Should be >= 1. Default = 1.'''

    capacity: float = Column(Float)
    '''
    A multiplicative factor for calculating the capacity constraint. Should be >= 1.
    Default = 1. Note, if this is not paired with fixed_capacity_site_number, then the capacity
    changes as a function of number of precincts.
    '''

    driving: bool = Column(Boolean)
    ''' Driving distances used if True and distance file exists in correct location '''

    fixed_capacity_site_number: int = Column(Integer)
    '''
    If default number of open precincts if one wants to hold the number
    of people that can go to a location constant (as opposed to a function of the number of locations).
    '''

    created_at: DateTime = Column(DateTime, nullable=False, default=current_time_utc)
    ''' The DateTime this model config was created. '''

    # Relations
    model_runs: Mapped[List['ModelRun']] = relationship(back_populates='model_config')
    ''' The runs that were used against this model configuration '''


    def generate_id(self) -> str:
        '''
        Returns an id for this config by creating a sha1 hash from
        the serialized column values.
        '''
        column_data = {}
        for column in self.__table__.columns:
            column_name = column.name
            if column_name in ['id', 'created_at', 'model_runs']:
                # don't include existing ids, dates, or mappings in serialization since it
                # will throw off the hash generation
                continue
            column_data[column_name] = getattr(self, column_name)

        serialized_data = json.dumps(column_data, sort_keys=True)
        hash_object = hashlib.sha1(serialized_data.encode())

        print(serialized_data)
        hex_dig = hash_object.hexdigest()
        return hex_dig

    def __repr__(self):
        year = ','.join(self.year)
        # pylint: disable-next=line-too-long
        return f"ModelConfig(id={self.id}, config_set='{self.config_set}', config_name='{self.config_name}', location='{self.location}', years='{year}')"


class ModelRun(ModelBase):
    ''' A SQLAlchemy record of a model run against an existing ModelConfig config.  '''

    __tablename__ = 'model_runs'

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        server_default=text('GENERATE_UUID()'),
        nullable=False,
    )
    ''' The UUID id of this this ModelRun object. '''

    username: str = Column(String(256))
    ''' The username of the person that executed this run. '''

    commit_hash: str = Column(String(256))
    ''' The git hash that this run was made with. '''

    created_at: DateTime = Column(DateTime, nullable=False, default=current_time_utc)
    ''' The time that this model run instance was created. '''

    success: bool = Column(Boolean, nullable=False, default=False)

    # Relations
    model_config_id = mapped_column(ForeignKey('model_configs.id'), nullable=False)
    ''' The ModelConfig id that this run is the result of '''

    model_config: Mapped['ModelConfig'] = relationship(back_populates='model_runs')
    ''' The ModelConfig instance that this run is the result of '''

    def __repr__(self):
        # pylint: disable-next=line-too-long
        return f"ModelRun(id={self.id}, model_config_id='{self.model_config_id}', username='{self.username}', created_at='{self.created_at}')"
