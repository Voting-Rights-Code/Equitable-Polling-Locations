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
state_precincts <- extract_county_precincts(STATE_PRECINCT_SOURCE_FILE, COUNTY_NAME, CRS_PROJECTION)

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
    STATE_PRECINCT_SOURCE_FILE,
    LOCATION
  )
} else {
  precincts_resolved <- state_precincts
}

###### Step 3: Extract and validate the county's blocks#######

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

######
#Step 4: associate blocks with (dominant) precincts 
#flag if a flag has 50-90% of its area outside a precints
#and write to file
#flagged_assigned_blocks
#######

block_precinct_intersection <- compute_block_precinct_overlaps(
  precincts_resolved, county_blocks, p3_population, AREA_CRS
)

block_precinct_assignment <- assign_block_to_dominant_precinct(block_precinct_intersection)

names(block_precinct_assignment)[names(block_precinct_assignment) == "geometry"] <- "block_geometry"
st_geometry(block_precinct_assignment) <- "block_geometry"

# write every asignment flagged block -- populated or not -- file
st_write(
block_precinct_assignment %>%
    filter(flagged == TRUE),
  file.path(precinct_analysis_output_folder, "flagged_assigned_blocks.gpkg"), append = FALSE
)

######
# Step 5: For further validation, of state precinct maps
# write every (block, precinct) pair with more than 5% overlap -- one row
# per precinct a block significantly overlaps
# flagged_overlapping_blocks
#######
overlapping_blocks <- flag_overlapping_blocks(block_precinct_intersection)

st_write(
  overlapping_blocks %>% filter(flagged == TRUE),
  file.path(precinct_analysis_output_folder, "flagged_overlapping_blocks.gpkg"), append = FALSE
)

######
# Step 6: flag precincts with zero population, either because all
# assigned block have no population, or because there are no assigned
# blocks.
#######
precinct_population <- data.table(st_drop_geometry(block_precinct_assignment))[
  , .(total_population = sum(total_population), assigned_blocks = .N), by = Precinct_I
]

precincts_resolved_with_population <- merge(
  precincts_resolved, precinct_population,
  by = "Precinct_I", all.x = TRUE, sort = FALSE
)
precincts_resolved_with_population <- precincts_resolved_with_population %>%
  mutate(unpopulated_precinct = is.na(total_population) | total_population == 0)

st_write(
  precincts_resolved_with_population %>% filter(unpopulated_precinct == TRUE),
  file.path(precinct_analysis_output_folder, "flagged_unpopulated_precincts.gpkg"), append = FALSE
)

###### Step 7: flag blocks far from their assigned polling location #######
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

