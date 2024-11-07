'''
    models/user.py
'''
# pylint: disable=invalid-name

from sqlalchemy import Column, String, Integer, Float
from sqlalchemy_main import ModelBase

class EDES(ModelBase):
    ''' Configuration record  '''

    __tablename__ = 'edes'

    id = Column(Integer, autoincrement=True, primary_key=True)
    demographic = Column(String(256))
    weighted_dist = Column(Float)
    avg_dist = Column(Float)
    demo_res_obj_summand = Column(Float)
    demo_pop = Column(Integer)
    avg_kp_weight = Column(Float)
    y_ede = Column(Float)
    config_name = Column(String(256))
    config_set = Column(String(256))
