'''
    models/precint_distance.py
'''

from sqlalchemy import Column, String, Integer, Float, text

from sqlalchemy_main import ModelBase
from utils import generate_uuid

class PrecintDistance(ModelBase):
    ''' Residence distance SQLAlchemy record. '''

    __tablename__ = 'precinct_distances'

    id: str = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        server_default=text('GENERATE_UUID()'),
        nullable=False,
    )
    model_run_id: str = Column(String(36), nullable=False)
    id_dest: str = Column(String(256))
    demographic: str = Column(String(256))
    weighted_dist: float = Column(Float)
    demo_pop: int = Column(Integer)
    avg_dist: float = Column(Float)
    source: str = Column(String(256))

    def __repr__(self):
        return f"PrecintDistance(id={self.id}, model_run_id='{self.model_run_id}', demographic='{self.demographic}')"
