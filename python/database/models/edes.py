'''
    models/edes.py
'''
# pylint: disable=invalid-name

from sqlalchemy import Column, String, Integer, Float, text

from python.database.sqlalchemy_main import ModelBase
from python.utils import generate_uuid

class EDES(ModelBase):
    ''' EDES SQLAlchemy record. '''

    __tablename__ = 'edes'

    id: str = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        server_default=text('GENERATE_UUID()'),
        nullable=False
    )

    model_run_id: str = Column(String(36), nullable=False)
    demographic: str = Column(String(256))
    weighted_dist: float = Column(Float)
    avg_dist: float = Column(Float)
    demo_res_obj_summand: float = Column(Float)
    demo_pop: int = Column(Integer)
    avg_kp_weight: float = Column(Float)
    y_ede: float = Column(Float)
    source: str = Column(String(256))

    def __repr__(self):
        return f"EDES(id={self.id}, model_run_id='{self.model_run_id}', demographic='{self.demographic}')"

