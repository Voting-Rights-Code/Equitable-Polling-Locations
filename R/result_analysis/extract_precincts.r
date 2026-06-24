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
# this file. The config's contents will grow as more steps are added to this
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




###### Step 1: extract and validate the county's precincts#######
county_precincts <- extract_county_precincts(PRECINCT_SOURCE_FILE, COUNTY_NAME)

stopifnot(
  "Precinct count does not match EXPECTED_PRECINCT_COUNT in the config file" =
    nrow(county_precincts) == EXPECTED_PRECINCT_COUNT
)

county_precincts <- county_precincts[, c("Precinct_I", "County_Nam", "USER_POLL_")]
county_precincts_proj <- st_transform(county_precincts, AREA_CRS)

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
  county_precincts, county_blocks, p3_population, AREA_CRS
)

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

