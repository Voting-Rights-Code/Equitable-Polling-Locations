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
COUNTY_PROVIDES_PRECINCT_DATA <- FALSE
COUNTY_PROVIDED_PRECINCT_FILE <- "temp/Precincts_by_Location.csv"
COUNTY_PRECINCT_LOCATION_NAME_COL <- "Polling Place Name"
COUNTY_PRECINCT_ADDRESS_COL <- "Polling Location Address"

########
# For testing
########
#EXPECTED_PRECINCT_COUNT <- 44

########
# Block geometry, for Step 2 (issue #267)
########
BLOCK_GEOMETRY_FILES <- "tl_2020_54061_tabblock20"
