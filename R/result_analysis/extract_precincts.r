library(sf)
library(data.table)
library(here)
library(dplyr)
library(ggplot2)

setwd(here())
source("R/result_analysis/utility_functions/shape_extraction_functions.r")

#######
# Read in command line arguments
# A config file must be given to get the location-specific constants for the
# extraction to be run. To extract a different county or state, add a new
# config file under R/result_analysis/Extraction_configs/ instead of editing
# this file. 
# TODO: The config's contents will grow as more steps are added to this
# script.
#######

#args <- commandArgs(trailingOnly = TRUE)
#if (length(args) != 1) {
#  stop("Must enter exactly one config file")
#} else {
#  config_path <- paste0("R/result_analysis/Extraction_configs/", args[1])
#  source(config_path)
#}

###
# For inline testing only
###
source("R/result_analysis/Extraction_configs/Monongalia_County_WV.r")

########
# Constants
########
CRS_PROJECTION <- 4326

#output folder name
precinct_analysis_output_folder <- file.path("precinct_analysis_outputs", LOCATION)
if (!file.exists(file.path(here(), precinct_analysis_output_folder))) {
  dir.create(file.path(here(), precinct_analysis_output_folder), recursive = TRUE)
}


###### Step 1: extract and validate the county's precincts#######
state_precincts <- extract_county_precincts(STATE_PRECINCT_STABLE_FILE, COUNTY_NAME, CRS_PROJECTION)

state_precincts <- state_precincts[, c("Precinct_I", "County_Nam", "USER_POLL_")]

names(state_precincts)[names(state_precincts) == "geometry"] <- "precinct_geometry"
st_geometry(state_precincts) <- "precinct_geometry"


###### 
# Step 2: reconcile county-provided precinct data 
# Assume that the county provided precinct data (if it exists)
# is correct. The reconciliation is to get the state data to match it. 
# Changes are made to the state file
#######

#If the county provides precinct data, 
#reconcile it with the state provided precinct data
if (COUNTY_PROVIDES_PRECINCT_DATA) {
  precincts_resolved <- reconcile_state_precinct_data(
    COUNTY_PROVIDED_PRECINCT_FILE,
    COUNTY_PRECINCT_COLUMN_NAMES,
    COUNTY_POLLING_LOCATION_NAME_COL,
    COUNTY_POLLING_LOCATION_ADDRESS_COL,
    state_precincts,
    COUNTY_NAME,
    STATE_PRECINCT_STABLE_FILE,
    LOCATION
  )
} else {
  precincts_resolved <- state_precincts
}

###### Step 3: flag blocks far from their assigned polling location #######
# 5 miles in meters. Explicit stand-in for "more than a 15-minute drive"
# until real drive-time data exists.
# TODO(#271): replace with a time-based threshold once driving *time* (not
# just distance) is available.
DISTANCE_FLAG_THRESHOLD_M <- 8046.72

#read in block assignment and manual corrections.
block_precinct_assignment <- st_read(
  file.path(precinct_analysis_output_folder, "block_precinct_assignment.gpkg")
)

crosswalk_path <- file.path(precinct_analysis_output_folder, "precinct_polling_location_crosswalk.csv")
state_county_crosswalk <- if (file.exists(crosswalk_path)) {
  fread(crosswalk_path)
} else {
  # no correction script has ever run for this county -- every precinct's
  # as-provided USER_POLL_ is already correct, so an empty crosswalk (every
  # block falls through to its own USER_POLL_) is the right default, not an error.
  data.table(Precinct_I = character(0), resolved_polling_location = character(0))
}

#read in block demographics
p3_file_path <- file.path(REDISTRICTING_FOLDER, LOCATION, "DECENNIALPL2020.P3-Data.csv")
p4_file_path <- file.path(REDISTRICTING_FOLDER, LOCATION, "DECENNIALPL2020.P4-Data.csv")
block_demographics <- get_block_demographics(p3_file_path, p4_file_path)

distance_flagged_blocks <- flag_distant_blocks(
  block_precinct_assignment, state_county_crosswalk, block_demographics,
  build_driving_distances_file_path(LOCATION),
  DISTANCE_FLAG_THRESHOLD_M
)

distance_flagged_blocks_path <- file.path(precinct_analysis_output_folder, "distance_flagged_blocks.csv")
fwrite(distance_flagged_blocks, distance_flagged_blocks_path)

###### Step 4: plot county-level distance heat map #######

# choropleth mode
make_demo_distance_heat_map(
  block_precinct_assignment, distance_flagged_blocks,
  precincts_resolved, demo_pop = NULL
)

# dot mode: one map per demographic of interest
make_demo_distance_heat_map(
  block_precinct_assignment, distance_flagged_blocks,
  precincts_resolved, demo_pop = "total_population"
)

make_demo_distance_heat_map(
  block_precinct_assignment, distance_flagged_blocks,
  precincts_resolved, demo_pop = "black"
)
