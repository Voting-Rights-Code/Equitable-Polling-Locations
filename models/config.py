'''
    models/user.py
'''

from sqlalchemy import Column, String, Integer, Float, DateTime
from sqlalchemy_main import ModelBase

class Config(ModelBase):
    ''' Configuration record  '''

    __tablename__ = 'configs'

    id = Column(Integer, autoincrement=True, primary_key=True)
    config_name = Column(String(256))
    location = Column(String(256))
    config_set = Column(String(256))
    year = Column(String(256))
    bad_types = Column(String(256))
    beta = Column(Float)
    time_limit = Column(Float)
    capacity = Column(Float)
    precincts_open = Column(Integer)
    max_min_mult = Column(Float)
    maxpctnew = Column(Float)
    minpctold = Column(Float)
    commit_hash = Column(String(256))
    run_time = Column(DateTime)
