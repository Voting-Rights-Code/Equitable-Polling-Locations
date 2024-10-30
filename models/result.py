'''
    models/user.py
'''

from sqlalchemy import Column, String, Integer, Float
from sqlalchemy_main import ModelBase

class Result(ModelBase):
    ''' Configuration record  '''

    __tablename__ = 'results'

    id = Column(Integer, autoincrement=True, primary_key=True)
    id_orig = Column(String(256))
    id_dest = Column(String(256))
    distance_m = Column(Float)
    address = Column(String(256))
    dest_lat = Column(Float(256))
    dest_lon = Column(Float(256))
    orig_lat = Column(Float(256))
    orig_lon = Column(Float(256))
    location_type = Column(String(256))
    dest_type = Column(String(256))
    population = Column(Integer)
    hispanic = Column(Integer)
    non_hispanic = Column(Integer)
    white = Column(Integer)
    black = Column(Integer)
    native = Column(Integer)
    asian = Column(Integer)
    pacific_islander = Column(Integer)
    other = Column(Integer)
    multiple_races = Column(Integer)
    weighted_dist = Column(Float)
    kp_factor = Column(Float)
    new_location = Column(Integer)
    matching = Column(Integer)
    config_name = Column(String(256))
    config_set = Column(String(256))
