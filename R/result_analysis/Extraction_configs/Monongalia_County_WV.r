########
# Location data
########

LOCATION <- "Monongalia_County_WV"
COUNTY_NAME <- sub("\\_.*", "", LOCATION)

STATE_PRECINCT_SOURCE_FILE <- "datasets/precincts/West_Virginia_20260424_wmA84/VotingPrecincts_20260424_wmA84.shp"
COUNTY_PRECINCT_SOURCE_FILE <- paste0("datasets/polling/", LOCATION, "/", LOCATION, "_potential_locations.csv")

########
# County-provided precinct/polling-location reconciliation (#282)
########
#Did the county provide precinct <-> polling location data
COUNTY_PROVIDES_PRECINCT_DATA <- TRUE 
#if so, where is it located
#TODO: what happens if this isn't provided? "null? error handling?"
COUNTY_PROVIDED_PRECINCT_FILE <- "temp/Precincts_by_Location.csv"
#Column name of the polling location
COUNTY_POLLING_LOCATION_NAME_COL <- "Polling Place Name"
COUNTY_POLLING_LOCATION_ADDRESS_COL <- "Polling Location Address"
COUNTY_PRECINCT_COLUMN_NAMES <- c("Prec", "Prec", "Prec", "Prec", "Prec", "Prec")

########
# For testing
########
#EXPECTED_PRECINCT_COUNT <- 44

########
# Block geometry, for Step 2 (issue #267)
########
BLOCK_GEOMETRY_FILES <- "tl_2020_54061_tabblock20"

########
# Driving distances, for Step 6 (issue #269)
########
DRIVING_DISTANCE_SUFFIX <- "_driving_distances.csv"
DRIVING_DISTANCES_FILE <- paste0("datasets/driving/", LOCATION, "/", LOCATION, DRIVING_DISTANCE_SUFFIX)
