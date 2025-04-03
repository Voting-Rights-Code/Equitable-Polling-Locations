'''
    models/data_source_polling_location.py
'''

from typing import List

from sqlalchemy import Boolean, Column, String, Integer, Float, DateTime, ForeignKey, text
from sqlalchemy.orm import mapped_column, Mapped, relationship

from python.database.sqlalchemy_main import ModelBase
from python.utils import current_time_utc, generate_uuid

# Questions: do we need early vote flag? - no goes into location type
# Better name? e.g. county_locations - no
# Can PollingLocationOnly just be a view of PollingLocation and/or do we need both in the DB - review workflow, maybe?  esp if the import itself makes the not _only file instead of model run
#     will have to think about impact on distance tables
# Can we avoid generating county_locations on run and only do it on import?  - yes (see above)

# are we still mixing these in polling_locations (the second type are centroids id_dest becomes block group): - these should be in the same file
# 68,450150201011000,Lebanon Mens' Club,30139.3392901949,Berkeley_County_SC,"1188 Lebanon Rd, Ridgeville, SC 29472",33.140979,-80.21408,33.4115614,-80.1950604,polling_2022_2020_2014_2016_2018,polling,0,0,0,0,0,0,0,0,0,0,haversine distance
# 69,450150201011000,450150201011,1154.17894775204,Berkeley_County_SC,"",33.413041,-80.1827525,33.4115614,-80.1950604,bg_centroid,bg_centroid,0,0,0,0,0,0,0,0,0,0,haversine distance
# BG centroid get added to short file as orgins
# Build source handles building long file (in model_data.py)


LOCATION_TYPE_CONTAINED_IN_CITY = 'contained_in_city'
LOCATION_TYPE_INTERSECTING_CITY = 'intersecting_city'
LOCATION_TYPE_CITY = 'city'
LOCATION_TYPE_COUNTY = 'county'

class PollingLocationSet(ModelBase):
    ''' Configuration SQLAlchemy record  '''

    __tablename__ = 'polling_locations_sets'

    id: str = Column(
        String(36),
        primary_key=True,
        default=generate_uuid,
        server_default=text('GENERATE_UUID()'),
        nullable=False
    )

    location: str = Column(String(256), nullable=False)
    ''' The name of the polling location set - TODO Rename this from name -> location'''

    election_year: str = Column(String(4), nullable=False)
    ''' The year the polling locations are in refrence to '''

    created_at: DateTime = Column(DateTime, nullable=False, default=current_time_utc)
    ''' The DateTime this model config was created. '''

    polling_locations_only: Mapped[List['PollingLocationOnly']] = relationship(back_populates='polling_locations_set')
    ''' The runs that were used against this model configuration '''

    polling_locations: Mapped[List['PollingLocation']] = relationship(back_populates='polling_locations_set')
    ''' The runs that were used against this model configuration '''

    def __repr__(self):
        # pylint: disable-next=line-too-long
        return f"PollingLocationSet(id={self.id}, election_year='{self.election_year}', location='{self.location}')"


class PollingLocationOnly(ModelBase):
    ''' Configuration SQLAlchemy record  '''

    __tablename__ = 'polling_locations_only'

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
    polling_locations_set_id = mapped_column(ForeignKey('polling_locations_sets.id'), nullable=False)
    ''' The PollingLocationSet id that this PollingLocationOnly belongs to '''

    polling_locations_set: Mapped['PollingLocationSet'] = relationship(back_populates='polling_locations_only')
    ''' The PollingLocationSet instance that this PollingLocationOnly belongs to '''

class PollingLocation(ModelBase):
    ''' Configuration SQLAlchemy record  '''

    __tablename__ = 'polling_locations'

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
    log_distance: bool = Column(Boolean, nullable=False)
    driving: bool = Column(Boolean, nullable=False)
    source: str = Column(String(256), nullable=False)

    # Relations
    polling_locations_set_id = mapped_column(ForeignKey('polling_locations_sets.id'), nullable=False)
    ''' The PollingLocationSet id that this PollingLocationOnly belongs to '''

    polling_locations_set: Mapped['PollingLocationSet'] = relationship(back_populates='polling_locations')
    ''' The PollingLocationSet instance that this PollingLocationOnly belongs to '''