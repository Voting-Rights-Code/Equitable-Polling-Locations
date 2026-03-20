'''
    models/data_source_polling_location.py
'''

from typing import List

from sqlalchemy import Boolean, Column, String, Integer, Float, DateTime, ForeignKey, text
from sqlalchemy.orm import mapped_column, Mapped, relationship

from python.database.sqlalchemy_main import ModelBase
from python.utils import current_time_utc, generate_uuid

from .driving_distances import DrivingDistancesSet

LOCATION_TYPE_CONTAINED_IN_CITY = 'contained_in_city'
LOCATION_TYPE_INTERSECTING_CITY = 'intersecting_city'


class PotentialLocationsSet(ModelBase):
    ''' PotentialLocationsSet SQLAlchemy record  '''

    __tablename__ = 'potential_locations_sets'

    id: str = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        server_default=text('GENERATE_UUID()'),
        nullable=False
    )

    location: str = Column(String(256), nullable=False)
    ''' The name of the polling location set '''

    created_at: DateTime = Column(DateTime, nullable=False, default=current_time_utc)
    ''' The DateTime this model config was created. '''

    potential_locations: Mapped[List['PotentialLocations']] = relationship(back_populates='potential_locations_set')
    ''' The runs that were used against this model configuration '''

    distance_data_sets: Mapped[List['DistanceDataSet']] = relationship(back_populates='potential_locations_set')
    ''' The sets of polling locations that are built off of this PollingLocationOnlySet instance '''

    def __repr__(self):
        # pylint: disable-next=line-too-long
        return f"PotentialLocationsSet(id={self.id}, election_year='{self.election_year}', location='{self.location}')"


class PotentialLocations(ModelBase):
    ''' PotentialLocations SQLAlchemy record  '''

    __tablename__ = 'potential_locations'

    id: str = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        server_default=text('GENERATE_UUID()'),
        nullable=False
    )

    location: str = Column(String(256), nullable=False)
    address: str = Column(String(256), nullable=False)
    location_type: str = Column(String(256), nullable=False)
    lat_lon: str = Column(String(256), nullable=False) # Note use lon, not long *

    # Relations
    potential_locations_set_id = mapped_column(ForeignKey('potential_locations_sets.id'), nullable=False)
    ''' The PotentialLocations.id that this PotentialLocations belongs to '''

    potential_locations_set: Mapped['PotentialLocationsSet'] = relationship(back_populates='potential_locations')
    ''' The PotentialLocations instance that this PotentialLocations belongs to '''



class DistanceDataSet(ModelBase):
    ''' DistanceDataSet SQLAlchemy record  '''

    __tablename__ = 'distance_data_sets'

    id: str = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        server_default=text('GENERATE_UUID()'),
        nullable=False
    )

    location: str = Column(String(256), nullable=False)
    ''' The name of the polling location set'''

    census_year: str = Column(String(4), nullable=False)
    ''' The census year the polling locations block groups are in refrence to '''

    created_at: DateTime = Column(DateTime, nullable=False, default=current_time_utc)
    ''' The DateTime this model config was created. '''

    log_distance: bool = Column(Boolean, nullable=False)

    driving: bool = Column(Boolean, nullable=False)

    # Relations
    potential_locations_set_id = mapped_column(ForeignKey('potential_locations_sets.id'), nullable=False)
    ''' The PotentialLocationsSet id that this DistanceDataSet is generated from. '''

    potential_locations_set: Mapped['PotentialLocationsSet'] = relationship(back_populates='distance_data_sets')
    ''' The PotentialLocationsSet instance that this DistanceDataSet is generated from. '''

    driving_distance_set_id = mapped_column(ForeignKey('driving_distance_sets.id'), nullable=True)
    ''' The DrivingDistancesSet id that this PollingLocationSet is generated from. Null if driving is set to False. '''

    driving_distance_set: Mapped['DrivingDistancesSet'] = relationship()
    ''' The DrivingDistancesSet instance that this PollingLocationSet is generated from. Null if driving is set to False. '''

    distance_data: Mapped[List['DistanceData']] = relationship(back_populates='distance_data_set')
    ''' The polling locations in this PollingLocationSet '''

    def __repr__(self):
        # pylint: disable-next=line-too-long
        return f"PollingLocationSet(id={self.id}, census_year='{self.census_year}', location='{self.location}', driving={self.driving}, log_distance={self.log_distance})"



class DistanceData(ModelBase):
    ''' DistanceData SQLAlchemy record  '''

    __tablename__ = 'distance_data'

    id: str = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        server_default=text('GENERATE_UUID()'),
        nullable=False
    )

    id_orig: str = Column(String(256), nullable=False)
    id_dest: str = Column(String(256), nullable=False)
    distance_m: float = Column(Float, nullable=True)
    address: str = Column(String(256), nullable=False)
    dest_lat: float = Column(Float, nullable=False)
    dest_lon: float = Column(Float, nullable=False)
    orig_lat: float = Column(Float, nullable=False)
    orig_lon: float = Column(Float, nullable=False)
    location_type: str = Column(String(256), nullable=False)
    dest_type: str = Column(String(256), nullable=False)
    population: int = Column(Integer, nullable=False)
    hispanic: int = Column(Integer, nullable=False)
    non_hispanic: int = Column(Integer, nullable=False)
    white: int = Column(Integer, nullable=False)
    black: int = Column(Integer, nullable=False)
    native: int = Column(Integer, nullable=False)
    asian: int = Column(Integer, nullable=False)
    pacific_islander: int = Column(Integer, nullable=False)
    other: int = Column(Integer, nullable=False)
    multiple_races: int = Column(Integer, nullable=False)
    source: str = Column(String(256), nullable=False)

    # Relations
    distance_data_set_id = mapped_column(ForeignKey('distance_data_sets.id'), nullable=False)
    ''' The DistanceDataSet id that this DistanceData belongs to '''

    distance_data_set: Mapped['DistanceDataSet'] = relationship(back_populates='distance_data')
    ''' The DistanceDataSet instance that this DistanceData belongs to '''
