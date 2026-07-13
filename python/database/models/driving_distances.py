'''
    models/driving_distances.py
'''

from typing import List

from sqlalchemy import Column, String, Float, DateTime, ForeignKey, text
from sqlalchemy.orm import mapped_column, Mapped, relationship

from ..sqlalchemy_main import ModelBase
from python.utils import current_time_utc, generate_uuid


class DrivingDistancesSet(ModelBase):
    ''' DrivingDistancesSet SQLAlchemy record  '''

    __tablename__ = 'driving_distance_sets'

    id: str = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        server_default=text('GENERATE_UUID()'),
        nullable=False
    )

    census_year: str = Column(String(4), nullable=False)
    ''' The year of the driving distance source data  '''

    map_source_date: str = Column(String(8), nullable=False)
    ''' The date of the driving distance source data, such as the Open Street Map data '''

    location: str = Column(String(256), nullable=False)

    created_at: DateTime = Column(DateTime, nullable=False, default=current_time_utc)
    ''' The DateTime this model DrivingDistancesSet was created. '''

    driving_distances: Mapped[List['DrivingDistance']] = relationship(back_populates='driving_distance_set')
    ''' The driving distances for this DrivingDistancesSet '''

    def __repr__(self):
        # pylint: disable-next=line-too-long
        return f"DrivingDistanceSet(id={self.id}, census_year='{self.census_year}', map_source_date='{self.map_source_date}', location='{self.location}')"


class DrivingDistance(ModelBase):
    ''' DrivingDistance SQLAlchemy record  '''

    __tablename__ = 'driving_distances'

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
    driving_distance_set_id = mapped_column(ForeignKey('driving_distance_sets.id'), nullable=False)
    ''' The DrivingDistancesSet id that this Distance belongs to '''

    # pylint: disable-next=line-too-long
    driving_distance_set: Mapped['DrivingDistancesSet'] = relationship(back_populates='driving_distances')
    ''' The DrivingDistancesSet instance that this Distance belongs to '''

