"""
Constants for solver
"""

DISTANCE_M = 'distance_m'
POPULATION = 'population'
WHITE = 'white'
BLACK = 'black'
NATIVE = 'native'
ASIAN = 'asian'
HISPANIC = 'hispanic'

DEMOGRAPHIC = 'demographic'

DEMO_POP = 'demo_pop'

WEIGHTED_DIST = 'weighted_dist'

DISTANCE_M = 'distance_m'
AVG_DIST = 'avg_dist'
DEST_TYPE = 'dest_type'
ID_DEST = 'id_dest'
ID_ORIG = 'id_orig'

POLLING = 'polling'

LOCATION_TYPE = 'location_type'
NEW_LOCATION = 'new_location'

SOURCE = 'SOURCE'

SUM = 'sum'
MEAN = 'mean'
MAX = 'max'
MIN = 'min'
UNIQUE = 'unique'
OUTER = 'outer'
LEFT = 'left'
CROSS = 'cross'

UTF8 = 'utf-8'

EMPTY_STRING = ''

KP_FACTOR = 'kp_factor'

YEAR = 'year'
BAD_TYPES = 'bad_types'
PENALIZED_SITES = 'penalized_sites'

DB_ID = 'db_id'
COMMIT_HASH = 'commit_hash'
RUN_TIME = 'run_time'
CONFIG_FILE_PATH = 'config_file_path'
LOG_FILE_PATH = 'log_file_path'
MAP_SOURCE_DATE = 'map_source_date'
LOCATION_SOURCE = 'location_source'


# Dtype related constants
DTYPE_STR = 'str'

# Location data related constants
LOC_LOCATION = 'Location'
LOC_ADDRESS = 'Address'
LOC_LOCATION_TYPE = 'Location type'
LOC_LAT_LON = 'Lat, Long'
LOC_LATITUDE = 'Latitude'
LOC_LONGITUDE = 'Longitude'

LOC_DEST_TYPE_POLLING = 'polling'
LOC_DEST_TYPE_POTENTIAL = 'potential'

LOC_TYPE_POTENTIAL = 'Potential'
LOC_TYPE_CENTROID = 'centroid'

# Census data related constants
CEN_GEO_ID = 'GEO_ID'
CEN_NAME = 'NAME'

CEN_P3_001N = 'P3_001N'
''' Total population '''

CEN_P3_003N = 'P3_003N'
''' White alone '''

CEN_P3_004N = 'P3_004N'
''' Black or African American alone '''

CEN_P3_005N = 'P3_005N'
''' American Indian or Alaska Native alone '''

CEN_P3_006N = 'P3_006N'
''' Asian alone '''

CEN_P3_007N = 'P3_007N'
''' Native Hawaiian and Other Pacific Islander alone '''

CEN_P3_008N = 'P3_008N'
''' Some other race alone '''

CEN_P3_009N = 'P3_009N'
''' Two or More Races '''

CEN_P4_001N = 'P4_001N'
''' Total population '''

CEN_P4_002N = 'P4_002N'
''' Total hispanic '''

CEN_P4_003N = 'P4_003N'
''' Total non_hispanic '''

CEN_POP_DIFF = 'Pop_diff'

# Census Block related constants
BLK_GEOID20 = 'GEOID20'
BLK_INTPTLAT20 = 'INTPTLAT20'
BLK_INTPTLON20 = 'INTPTLON20'

BLK_BG_CENTROID = 'bg_centroid'
BLK_POP_DIFF = 'Pop_diff'

# Model data source Related constants
SRC_LOCATION  = 'location'
SRC_ADDRESS = 'address'
SRC_DEST_LAT = 'dest_lat'
SRC_DEST_LON = 'dest_lon'
SRC_ORIG_LAT = 'orig_lat'
SRC_ORIG_LON = 'orig_lon'
SRC_LOCATION_TYPE = 'location_type'
SRC_DEST_TYPE = 'dest_type'
SRC_POPULATION = 'population'
SRC_HISPANIC = 'hispanic'
SRC_NON_HISPANIC = 'non_hispanic'
SRC_WHITE = 'white'
SRC_BLACK = 'black'
SRC_NATIVE = 'native'
SRC_ASIAN = 'asian'
SRC_PACIFIC_ISLANDER = 'pacific_islander'
SRC_OTHER = 'other'
SRC_MULTIPLE_RACES = 'multiple_races'
SRC_SOURCE = 'source'
SRC_WEIGHTED_DIST = 'weighted_dist'
SRC_DISTANCE_SQUARED = 'distance_squared'
SRC_DRIVING_DISTANCE = 'driving distance'
SRC_HAVERSINE_DISTANCE = 'haversine distance'
SRC_LOG_WITH_SPACE = 'log '

# Results related constants
RSLT_MATCHING = 'matching'
RSLT_SOURCE = 'source'
RSLT_DEMO_RES_OBJ_SUMMAND = 'demo_res_obj_summand'
RSLT_AVG_KP_WEIGHT = 'avg_kp_weight'
RSLT_Y_EDE = 'y_EDE'


# DB Column related constants
DB_LOCATION = 'location'
DB_ADDRESS = 'address'
DB_LOCATION_TYPE = 'location_type'
DB_LAT_LON = 'lat_lon'

# Solver related constants
SLV_MODEL2 = 'model2'
SLV_PENALTY = 'penalty'
