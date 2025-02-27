'''
    models/data_source_distance.py
'''

from typing import List

from sqlalchemy import Column, String, Float, DateTime, ForeignKey, text
from sqlalchemy.orm import mapped_column, Mapped, relationship

from ..sqlalchemy_main import ModelBase
from python.utils import current_time_utc, generate_uuid

# Call this DrivingDistances - it is always driving distance
LOCATION_TYPE_CITY = 'city'
LOCATION_TYPE_COUNTY = 'county'

class DistancesSet(ModelBase):
    ''' Configuration SQLAlchemy record  '''

    __tablename__ = 'distance_sets'


    # ID should be (lower case): [location]_[conty|city]_[state]_[census_year]_[map_source_year]


    id: str = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        server_default=text('GENERATE_UUID()'),
        nullable=False
    )

    name: str = Column(String(300), nullable=False)

    state: str = Column(String(2), nullable=False)

    location_type: str = Column(String(10), nullable=False)

    location: str = Column(String(256), nullable=False)

    census_year: str = Column(String(4), nullable=False)
    ''' The year of the distance source data  '''

    map_source_year: str = Column(String(4), nullable=False)
    ''' The year of the distance source data, such as the Open Street Map data '''

    created_at: DateTime = Column(DateTime, nullable=False, default=current_time_utc)
    ''' The DateTime this model config was created. '''

    distances: Mapped[List['Distance']] = relationship(back_populates='distance_set')
    ''' The distances for this DistancesSet '''

    @classmethod
    def normalize_name(cls, location: str, location_type: str, state: str, census_year: str, map_source_year: str) -> str:
        ''' Generate a normalized name for a DistancesSet '''

        return '_'.join([location, location_type, state, census_year, map_source_year]).replace(' ', '_').lower()

    def generate_name(self) -> str:
        ''' Generate a name for this DistancesSet '''

        return DistancesSet.normalize_name(self.location, self.location_type, self.state, self.census_year, self.map_source_year)


    def __repr__(self):
        # pylint: disable-next=line-too-long
        return f"DistanceSet(id={self.id}, name='{self.name}')"


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

