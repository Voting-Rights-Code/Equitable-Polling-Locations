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


###### Step 1: extract and validate the county's precincts#######
state_precincts <- extract_county_precincts(STATE_PRECINCT_SOURCE_FILE, COUNTY_NAME, CRS_PROJECTION)


###TODO: currently commented out due to the bug where precinct 73 has no population. see issue 283
#stopifnot(
#  "Precinct count does not match EXPECTED_PRECINCT_COUNT in the config file" =
#    nrow(state_precincts) == EXPECTED_PRECINCT_COUNT
#)

state_precincts <- state_precincts[, c("Precinct_I", "County_Nam", "USER_POLL_")]

names(state_precincts)[names(state_precincts) == "geometry"] <- "precinct_geometry"
st_geometry(state_precincts) <- "precinct_geometry"

state_precincts_proj <- st_transform(state_precincts, AREA_CRS)

###### Step 2: Extract and validate the county's blocks#######
#extract county blocks from the TIGER/Line shapefile
tiger_file_path <-  file.path(TIGER_FOLDER, LOCATION, paste0(BLOCK_GEOMETRY_FILES, ".shp"))
county_blocks <- get_shape_data( tiger_file_path)

#extract county blocks from the TIGER/Line shapefile
p3_file_path <- file.path(REDISTRICTING_FOLDER, LOCATION, "DECENNIALPL2020.P3-Data.csv")
p3_population <- fread(
  p3_file_path,
  header = FALSE, skip = 2,
  select = c(1, 3), col.names = c("GEO_ID", "total_population")
)

######Step 3: associate blocks with (dominant) precincts #######

block_precinct_assignment <- assign_block_to_dominant_precinct(
  state_precincts, county_blocks, p3_population, AREA_CRS
)

names(block_precinct_assignment)[names(block_precinct_assignment) == "geometry"] <- "block_geometry"
st_geometry(block_precinct_assignment) <- "block_geometry"

######Step 4: write assignment to file #######

# write every flagged block -- populated or not -- file
precinct_analysis_output_folder <- file.path("precinct_analysis_outputs", LOCATION)
if (!file.exists(file.path(here(), precinct_analysis_output_folder))) {
  dir.create(file.path(here(), precinct_analysis_output_folder), recursive = TRUE)
}

st_write(
block_precinct_assignment %>%
    filter(flagged == TRUE),
  file.path(precinct_analysis_output_folder, "flagged_assigned_blocks.gpkg"), append = FALSE
)

###### Step 5: reconcile county-provided precinct data #######
# In this step, we assume that the county provided precinct data (if it exists)
# is correct. The reconciliation is to get the state data to match it. 
# Changes are made to the state file


#If the county provides precinct data, 
#reconcile it with the state provided precinct data
if (COUNTY_PROVIDES_PRECINCT_DATA) {
  county_precincts_resolved <- reconciled_state_precinct_data(
    COUNTY_PROVIDED_PRECINCT_FILE,
    COUNTY_PRECINCT_COLUMN_NAMES,
    COUNTY_POLLING_LOCATION_NAME_COL,
    COUNTY_POLLING_LOCATION_ADDRESS_COL,
    state_precincts,
    COUNTY_NAME
  )
} else {
  county_precincts_resolved <- state_precincts
}

# Drop precincts with zero population, per block-level population data in
# block_precinct_assignment. TODO: until #283 is fixed, the
# dominant-block population heuristic can show real, populated precincts as
# zero (e.g. Monongalia_73), so this can't be fully relied on yet.
precinct_population <- data.table(st_drop_geometry(block_precinct_assignment))[
  , .(total_population = sum(total_population)), by = Precinct_I
]


county_precincts_resolved <- merge(
  county_precincts_resolved, precinct_population,
  by = "Precinct_I", sort = FALSE
)
county_precincts_resolved <- county_precincts_resolved[
  county_precincts_resolved$total_population > 0,
]
county_precincts_resolved$total_population <- NULL

###### Step 6: flag blocks far from their assigned polling location #######

# 5 miles in meters. Explicit stand-in for "more than a 15-minute drive"
# until real drive-time data exists.
# TODO(#271): replace with a time-based threshold once driving *time* (not
# just distance) is available.
DISTANCE_FLAG_THRESHOLD_M <- 8046.72

p4_file_path <- file.path(REDISTRICTING_FOLDER, LOCATION, "DECENNIALPL2020.P4-Data.csv")
block_demographics <- get_block_demographics(p3_file_path, p4_file_path)

distance_flagged_blocks <- flag_distant_blocks(
  block_precinct_assignment, block_demographics,
  build_driving_distances_file_path(LOCATION),
  build_potential_locations_file_path(LOCATION),
  DISTANCE_FLAG_THRESHOLD_M
)

distance_flagged_blocks_path <- file.path(precinct_analysis_output_folder, "distance_flagged_blocks.csv")
fwrite(distance_flagged_blocks, distance_flagged_blocks_path)

cat(sprintf(
  "Wrote %d-row distance-flagged block table to %s\n",
  nrow(distance_flagged_blocks), distance_flagged_blocks_path
))
