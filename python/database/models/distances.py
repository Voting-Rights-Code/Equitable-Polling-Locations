'''
    models/data_source_distance.py
'''

from typing import List

from sqlalchemy import Column, String, Float, Date, DateTime, ForeignKey, text
from sqlalchemy.orm import mapped_column, Mapped, relationship

from ..sqlalchemy_main import ModelBase
from python.utils import current_time_utc, generate_uuid

# TODO Call this DrivingDistances - it is always driving distance

class DistancesSet(ModelBase):
    ''' Configuration SQLAlchemy record  '''

    __tablename__ = 'distance_sets'

    id: str = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        server_default=text('GENERATE_UUID()'),
        nullable=False
    )

    census_year: str = Column(String(4), nullable=False)
    ''' The year of the distance source data  '''

    map_source_date: str = Column(String(8), nullable=False)
    ''' The date of the distance source data, such as the Open Street Map data '''

    location: str = Column(String(256), nullable=False)

    created_at: DateTime = Column(DateTime, nullable=False, default=current_time_utc)
    ''' The DateTime this model config was created. '''

    distances: Mapped[List['Distance']] = relationship(back_populates='distance_set')
    ''' The distances for this DistancesSet '''

    def __repr__(self):
        # pylint: disable-next=line-too-long
        return f"DistanceSet(id={self.id}, census_year='{self.census_year}', map_source_date='{self.map_source_date}', location='{self.location}')"


class Distance(ModelBase):
    ''' Configuration SQLAlchemy record  '''

    __tablename__ = 'distances'

    id: str = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        server_default=text('GENERATE_UUID()'),
        nullable=False
    )

    id_orig: str = Column(String(256), nullable=False)
    id_dest: str = Column(String(256), nullable=False)
    distance_m: float = Column(Float, nullable=False)
    source: str = Column(String(256), nullable=False)

      # Relations
    distance_set_id = mapped_column(ForeignKey('distance_sets.id'), nullable=False)
    ''' The DistancesSet id that this Distance belongs to '''

    # pylint: disable-next=line-too-long
    distance_set: Mapped['DistancesSet'] = relationship(back_populates='distances')
    ''' The DistancesSet instance that this Distance belongs to '''

