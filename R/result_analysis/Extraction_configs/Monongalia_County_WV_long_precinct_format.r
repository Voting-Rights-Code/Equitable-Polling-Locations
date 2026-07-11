########
# Location data
########

LOCATION <- "Monongalia_County_WV"
COUNTY_NAME <- sub("\\_.*", "", LOCATION)

######
#data set locations
######
STATE_PRECINCT_SOURCE_FILE <- "datasets/precincts/West_Virginia_20260424_wmA84/VotingPrecincts_20260424_wmA84.shp"

########
# County-provided precinct/polling-location reconciliation
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
COUNTY_PROVIDED_PRECINCT_FILE <- "temp/Precincts_by_Location_long.csv" #cannnot be null if COUNTY_PROVIDES_PRECINCT_DATA is TRUE
#details specific to the file
COUNTY_POLLING_LOCATION_NAME_COL <- "Polling Place Name" #cannnot be null if COUNTY_PROVIDES_PRECINCT_DATA is TRUE
COUNTY_POLLING_LOCATION_ADDRESS_COL <- "Polling Location Address" #cannnot be null if COUNTY_PROVIDES_PRECINCT_DATA is TRUE
COUNTY_PRECINCT_COLUMN_NAMES <- c("Precinct") #cannnot be null if COUNTY_PROVIDES_PRECINCT_DATA is TRUE

#check that proper file / columns names are added if and only if the county provides data
county_provided_data_names <- list(COUNTY_PROVIDED_PRECINCT_FILE, COUNTY_POLLING_LOCATION_NAME_COL,
                                    COUNTY_POLLING_LOCATION_ADDRESS_COL, COUNTY_PRECINCT_COLUMN_NAMES)
if (COUNTY_PROVIDES_PRECINCT_DATA) {
  if (any(sapply(county_provided_data_names, is.null))) {
    stop("None of COUNTY_PROVIDED_ file, precinct location name column, precinct address column or the columns indicating 
          assinged precincts can be null if COUNTY_PROVIDES_PRECINCT_DATA is TRUE")
  }
} else { #COUNTY_PROVIDES_PRECINCT_DATA is FALSE
  if (any(!sapply(county_provided_data_names, is.null))) {
    stop("All of COUNTY_PROVIDED_ file, precinct location name column, precinct address column and the columns indicating 
            assinged precincts must be null if COUNTY_PROVIDES_PRECINCT_DATA is FALSE")
  }
}

########
# For testing
########
#EXPECTED_PRECINCT_COUNT <- 44

########
# Block geometry, for Step 2  
########
BLOCK_GEOMETRY_FILES <- "tl_2020_54061_tabblock20"
