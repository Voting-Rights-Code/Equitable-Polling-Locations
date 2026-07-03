########
# Location data
########

LOCATION <- "Monongalia_County_WV"
COUNTY_NAME <- sub("\\_.*", "", LOCATION)

STATE_PRECINCT_SOURCE_FILE <- "datasets/precincts/West_Virginia_20260424_wmA84/VotingPrecincts_20260424_wmA84.shp"
COUNTY_PRECINCT_SOURCE_FILE <- paste0("datasets/polling/", LOCATION, "/", LOCATION, "_potential_locations.csv")

########
# County-provided data and associated labels.
########
COUNTY_PROVIDES_PRECINCT_DATA <- TRUE
COUNTY_PROVIDED_PRECINCT_FILE <- "temp/Precincts_by_Location.csv" #cannnot be null if COUNTY_PROVIDES_PRECINCT_DATA is TRUE
COUNTY_PRECINCT_LOCATION_NAME_COL <- "Polling Place Name" #cannnot be null if COUNTY_PROVIDES_PRECINCT_DATA is TRUE
COUNTY_PRECINCT_ADDRESS_COL <- "Polling Location Address" #cannnot be null if COUNTY_PROVIDES_PRECINCT_DATA is TRUE

#check that proper file / columns names are added if and only if the county provides data
county_provided_data_names <- c(COUNTY_PROVIDED_PRECINCT_FILE, COUNTY_PRECINCT_LOCATION_NAME_COL, 
                                                        COUNTY_PRECINCT_ADDRESS_COL) 
if (COUNTY_PROVIDES_PRECINCT_DATA) {
  if (any (is.null(county_provided_data_names))) {
    stop("COUNTY_PROVIDED_ file, precinct location name column, or precinct address column cannot be null 
        if COUNTY_PROVIDES_PRECINCT_DATA is TRUE")
  }
else { #COUNTY_PROVIDES_PRECINCT_DATA is FALSE
    if (any (!is.null(county_provided_data_names)))
    stop("COUNTY_PROVIDED_ file, precinct location name column, or precinct address columns must be null 
        if COUNTY_PROVIDES_PRECINCT_DATA is FALSE")

########
# For testing
########
#EXPECTED_PRECINCT_COUNT <- 44

########
# Block geometry, for Step 2 (issue #267)
########
BLOCK_GEOMETRY_FILES <- "tl_2020_54061_tabblock20"
