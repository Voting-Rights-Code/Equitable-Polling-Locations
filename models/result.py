'''
    models/result.py
'''

from sqlalchemy import Column, String, Integer, Float, text

from sqlalchemy_main import ModelBase
from utils import generate_uuid

class Result(ModelBase):
    ''' Configuration SQLAlchemy record  '''

    __tablename__ = 'results'

    id: str = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        server_default=text('GENERATE_UUID()'),
        nullable=False
    )
    model_run_id: str = Column(String(36), nullable=False)
    id_orig: str = Column(String(256))
    id_dest: str = Column(String(256))
    distance_m: float = Column(Float)
    haversine_m: float = Column(Float)
    county: float = Column(String(256))
    address: str = Column(String(256))
    dest_lat: float = Column(Float)
    dest_lon: float = Column(Float)
    orig_lat: float = Column(Float)
    orig_lon: float = Column(Float)
    location_type: str = Column(String(256))
    dest_type: str = Column(String(256))
    population: int = Column(Integer)
    hispanic: int = Column(Integer)
    non_hispanic: int = Column(Integer)
    white: int = Column(Integer)
    black: int = Column(Integer)
    native: int = Column(Integer)
    asian: int = Column(Integer)
    pacific_islander: int = Column(Integer)
    other: int = Column(Integer)
    multiple_races: int = Column(Integer)
    weighted_dist: float = Column(Float)
    kp_factor: float = Column(Float)
    new_location: int = Column(Integer)
    matching: int = Column(Integer)
    source: str = Column(String(256))

    def __repr__(self):
        # pylint: disable-next=line-too-long
        return f"Result(id={self.id}, model_run_id='{self.model_run_id}', county='{self.county}, address='{self.address}')"

