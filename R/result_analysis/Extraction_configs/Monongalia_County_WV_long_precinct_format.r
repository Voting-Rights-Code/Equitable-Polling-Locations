########
# Location data
########

LOCATION <- "Monongalia_County_WV"
COUNTY_NAME <- sub("\\_.*", "", LOCATION)

STATE_PRECINCT_SOURCE_FILE <- "datasets/precincts/West_Virginia_20260424_wmA84/VotingPrecincts_20260424_wmA84.shp"
COUNTY_PRECINCT_SOURCE_FILE <- paste0("datasets/polling/", LOCATION, "/", LOCATION, "_potential_locations.csv")

########
# County-provided precinct/polling-location reconciliation (#282)
#
# Same as Monongalia_County_WV.r, except COUNTY_PROVIDED_PRECINCT_FILE points
# at a long-format file (one row per precinct, via
# R/result_analysis/scratch_melt_precincts_long.r) instead of the original
# wide-format file (one row per polling location, with repeated "Prec"
# columns). Used to test whether the reconciliation pipeline handles a
# long-format county source file.
########
#Did the county provide precinct <-> polling location data
COUNTY_PROVIDES_PRECINCT_DATA <- TRUE
#if so, where is it located
#TODO: what happens if this isn't provided? "null? error handling?"
COUNTY_PROVIDED_PRECINCT_FILE <- "temp/Precincts_by_Location_long.csv"
#Column name of the polling location
COUNTY_POLLING_LOCATION_NAME_COL <- "Polling Place Name"
COUNTY_POLLING_LOCATION_ADDRESS_COL <- "Polling Location Address"
COUNTY_PRECINCT_COLUMN_NAMES <- c("Precinct")

########
# For testing
########
#EXPECTED_PRECINCT_COUNT <- 44

########
# Block geometry, for Step 2 (issue #267)
########
BLOCK_GEOMETRY_FILES <- "tl_2020_54061_tabblock20"
