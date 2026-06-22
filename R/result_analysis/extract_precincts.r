library(sf)
library(data.table)
library(here)

setwd(here())
source("R/result_analysis/utility_functions/shape_extraction_functions.r")

#######
# Read in command line arguments
# A config file must be given to get the location-specific constants for the
# extraction to be run. To extract a different county or state, add a new
# config file under R/result_analysis/Extraction_configs/ instead of editing
# this file. The config's contents will grow as more steps are added to this
# script.
#######

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) {
  stop("Must enter exactly one config file")
} else {
  config_path <- paste0("R/result_analysis/Extraction_configs/", args[1])
  source(config_path)
}

###
# For inline testing only
###
# source("R/result_analysis/Extraction_configs/Monongalia_County_WV.r")

########
# Constants
########
CRS_PROJECTION <- 4326


###### Step 1: extract and validate the county's precincts#######
county_precincts <- extract_county_precincts(PRECINCT_SOURCE_FILE, COUNTY_NAME, CRS_PROJECTION)

stopifnot(
  "Precinct count does not match EXPECTED_PRECINCT_COUNT in the config file" =
    nrow(county_precincts) == EXPECTED_PRECINCT_COUNT
)

cat(sprintf("Extracted %d precincts into memory.\n", nrow(county_precincts)))
