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
#source("R/result_analysis/Extraction_configs/Monongalia_County_WV.r")
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
  file.path(precinct_analysis_output_folder, "flagged_blocks.gpkg"), append = FALSE
)

###### Step 5: reconcile county-provided precinct data #######
#If the county provides precinct data, 
#reconcile it with the state provided precinct data
if (COUNTY_PROVIDES_PRECINCT_DATA) {
  provided_polls <- fread(COUNTY_PROVIDED_PRECINCT_FILE)

  #select column names form county based on config entries
  precinct_column_numbers <- which(names(provided_polls) %in% COUNTY_PRECINCT_COLUMN_NAMES)

  # Check that the names in the COUNTY_PRECINCT_COLUMN_NAMES config value
  # are all fields in the county provided data
  county_column_name_count <- c(table(names(provided_polls)[precinct_column_numbers]))
  config_column_name_count <- c(table(COUNTY_PRECINCT_COLUMN_NAMES))
  stopifnot(
    "The COUNTY_PRECINCT_COLUMN_NAMES count doesn't match the source file's matching column count" =
      identical(county_column_name_count, config_column_name_count)
  )

  unique_precinct_columns <- make.unique(names(provided_polls)[precinct_column_numbers])
  setnames(provided_polls, old = precinct_column_numbers, new = unique_precinct_columns)

  county_precincts_resolved <- reconcile_county_provided_precincts(
    provided_polls,
    precinct_columns = unique_precinct_columns,
    location_name_col = COUNTY_POLLING_LOCATION_NAME_COL,
    address_col = COUNTY_POLLING_LOCATION_ADDRESS_COL,
    state_precincts = state_precincts,
    county_name = COUNTY_NAME
  )
} else {
  # No county-provided data to reconcile against: fall back to dropping
  # precincts with zero population, per block-level population data in
  # block_precinct_assignment (#283 caveat: the dominant-block population
  # heuristic can show real, populated precincts as zero -- e.g.
  # Monongalia_73 -- so this fallback isn't fully trustworthy yet)
  precinct_population <- data.table(st_drop_geometry(block_precinct_assignment))[
    , .(total_population = sum(total_population)), by = Precinct_I
  ]

  county_precincts_resolved <- merge(
    state_precincts, precinct_population,
    by = "Precinct_I", sort = FALSE
  )
  county_precincts_resolved <- county_precincts_resolved[
    county_precincts_resolved$total_population > 0,
  ]
  county_precincts_resolved$total_population <- NULL
}
