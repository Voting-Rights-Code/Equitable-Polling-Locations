'''
    models/user.py
'''

from sqlalchemy import Column, String, Integer, Float
from sqlalchemy_main import ModelBase

class PrecintDistance(ModelBase):
    ''' Configuration record  '''

    __tablename__ = 'precinct_distances'

    id = Column(Integer, autoincrement=True, primary_key=True)
    id_dest = Column(String(256))
    demographic = Column(String(256))
    weighted_dist = Column(Float)
    demo_pop = Column(Integer)
    avg_dist = Column(Float)
    config_name = Column(String(256))
    config_set = Column(String(256))
