########
# Location data
########

LOCATION <- "Monongalia_County_WV"
COUNTY_NAME <- sub("\\_.*", "", LOCATION)

# Names corrected, but precinct-ID mappings not yet reconciled with the
# county (Granville 44 still assigned to the Fire Dept Bingo Hall, no
# Monongalia_2A/2B split). Used to exercise check_precinct_id_agreement()'s
# stop() error.
STATE_PRECINCT_SOURCE_FILE <- "datasets/precincts/West_Virginia_20260424_wmA84_old_precinct_ids/VotingPrecincts_20260424_wmA84_old_precinct_ids.shp"
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
