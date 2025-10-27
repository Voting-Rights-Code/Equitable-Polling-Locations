"""
Constants for solver
"""

UTF8 = 'utf-8'
''' Used for python file reads '''

DATA_SOURCE_DB = 'db'
DATA_SOURCE_CSV = 'csv'

EMPTY_STRING = ''
''' An empty string ( len(EMPTY_STRING) = 0 ). Used to clear out values in data frames. '''

# Pandas related constants
PD_SUM = 'sum'
PD_MEAN = 'mean'
PD_MAX = 'max'
PD_MIN = 'min'
PD_UNIQUE = 'unique'
PD_OUTER = 'outer'
PD_LEFT = 'left'
PD_CROSS = 'cross'
PD_DTYPE_STR = 'str'


# Model config related constants
CONFIG_YEAR = 'year'
CONFIG_BAD_TYPES = 'bad_types'
CONFIG_PENALIZED_SITES = 'penalized_sites'
CONFIG_DB_ID = 'db_id'
CONFIG_COMMIT_HASH = 'commit_hash'
CONFIG_RUN_TIME = 'run_time'
CONFIG_FILE_PATH = 'config_file_path'
CONFIG_LOG_FILE_PATH = 'log_file_path'
CONFIG_MAP_SOURCE_DATE = 'map_source_date'
CONFIG_LOCATION_SOURCE = 'location_source'

# Location only data related constants
LOC_ONLY_LOCATION = 'Location'
LOC_ONLY_ADDRESS = 'Address'
LOC_ONLY_LOCATION_TYPE = 'Location type'
LOC_ONLY_LAT_LON = 'Lat, Long'
LOC_ONLY_LATITUDE = 'Latitude'
LOC_ONLY_LONGITUDE = 'Longitude'

# Location data related column names
LOC_ID_ORIG = 'id_orig'
LOC_ID_DEST = 'id_dest'
LOC_SOURCE = 'source'
LOC_DISTANCE_M = 'distance_m'
LOC_ADDRESS = 'address'
LOC_DEST_LAT = 'dest_lat'
LOC_DEST_LON = 'dest_lon'
LOC_ORIG_LAT = 'orig_lat'
LOC_ORIG_LON = 'orig_lon'
LOC_LOCATION_TYPE = 'location_type'
LOC_HISPANIC = 'hispanic'
LOC_NON_HISPANIC = 'non_hispanic'
LOC_WHITE = 'white'
LOC_BLACK = 'black'
LOC_NATIVE = 'native'
LOC_ASIAN = 'asian'
LOC_PACIFIC_ISLANDER = 'pacific_islander'
LOC_OTHER = 'other'
LOC_MULTIPLE_RACES = 'multiple_races'
LOC_TOTAL_POPULATION = 'population'
LOC_WEIGHTED_DIST = 'weighted_dist'
LOC_DISTANCE_SQUARED = 'distance_squared'
LOC_DEST_TYPE = 'dest_type'


LOC_SOURCE_HAVERSINE_DISTANCE = 'haversine distance'
''' A type value for the LOC_LOCATION_TYPE field '''
LOC_SOURCE_DRIVING_DISTANCE = 'driving distance'
''' A type value for the LOC_LOCATION_TYPE field '''
LOC_SOURCE_LOG_WITH_SPACE = 'log '
''' A type value for the LOC_LOCATION_TYPE field that works with other types (e.g. "log haversine distance") '''
LOC_ONLY_LOCATION_TYPE_POTENTIAL_SUBSTR = 'Potential'
''' A flag in the field LOC_ONLY_LOCATION_TYPE indicating a potential location '''
LOC_ONLY_LOCATION_TYPE_CENTROID_SUBSTR = 'centroid'
''' A flag in the field LOC_ONLY_LOCATION_TYPE indicating a centroid '''
LOC_ONLY_DEST_TYPE_POLLING = 'polling'
LOC_ONLY_DEST_TYPE_POTENTIAL = 'potential'

LOCATION_TYPE_POTENTIAL_SUBSTR = 'Potential'
LOCATION_TYPE_CENTROID_SUBSTR = 'centroid'



# Census data related constants
CEN20_GEO_ID = 'GEO_ID'
CEN20_NAME = 'NAME'
CEN20_P3_TOTAL_POPULATION = 'P3_001N'
''' Total population '''
CEN20_P3_WHITE = 'P3_003N'
''' White alone '''
CEN20_P3_BLACK = 'P3_004N'
''' Black or African American alone '''
CEN20_P3_NATIVE = 'P3_005N'
''' American Indian or Alaska Native alone '''
CEN20_P3_ASIAN = 'P3_006N'
''' Asian alone '''
CEN20_P3_PACIFIC_ISLANDER = 'P3_007N'
''' Native Hawaiian and Other Pacific Islander alone '''
CEN20_P3_OTHER = 'P3_008N'
''' Some other race alone '''
CEN20_P3_MULTIPLE_RACES = 'P3_009N'
''' Two or More Races '''
CEN20_P4_TOTAL_POPULATION = 'P4_001N'
''' Total population '''
CEN20_P4_HISPANIC = 'P4_002N'
''' Total hispanic '''
CEN20_NON_HISPANIC = 'P4_003N'
''' Total non_hispanic '''

# Census Block related constants
TIGER20_GEOID_PREFIX = '1000000US'
TIGER20_GEOID20 = 'GEOID20'
TIGER20_INTPTLAT20 = 'INTPTLAT20'
TIGER20_INTPTLON20 = 'INTPTLON20'
TIGER20_BG_CENTROID = 'bg_centroid'
TIGER20_POP_DIFF = 'Pop_diff'


# Results related constants
RESULT_MATCHING = 'matching'
RESULT_DEMOGRAPHIC = 'demographic'
RESULT_DEMO_POP = 'demo_pop'
RESULT_DEMO_RES_OBJ_SUMMAND = 'demo_res_obj_summand'
RESULT_AVG_KP_WEIGHT = 'avg_kp_weight'
RESULT_Y_EDE = 'y_EDE'
RESULT_NEW_LOCATION = 'new_location'
RESULT_AVG_DIST = 'avg_dist'
RESULT_KP_FACTOR = 'kp_factor'

DOMAIN_WEIGHTED_DIST = 'weighted_dist'

# DB Column related constants
DB_LOCATION = 'location'
DB_ADDRESS = 'address'
DB_LOCATION_TYPE = 'location_type'
DB_LAT_LON = 'lat_lon'

# Solver related constants
SOLVER_MODEL2 = 'model2'
SOLVER_PENALTY = 'penalty'
