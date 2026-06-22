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

###### Step 2: verify precincts decompose into census blocks (#267) #######
county_blocks <- get_shape_data(
  file.path(TIGER_FOLDER, LOCATION, paste0(BLOCK_GEOMETRY_FILES, ".shp")),
  CRS_PROJECTION
)

cat(sprintf("Read %d census blocks into memory.\n", nrow(county_blocks)))

# assign the blocks intersecting a single precinct, tagged with that
# precinct's id, for combining across all precincts below
assign_blocks_to_precinct <- function(precinct_index) {
  precinct_row <- county_precincts[precinct_index, ]

  intersecting_blocks <- get_shapes_in_boundary(precinct_row, county_blocks, TRUE)
  cropped_blocks <- crop_to_boundary(precinct_row, intersecting_blocks)
  cropped_blocks$Precinct_I <- precinct_row$Precinct_I
  return(cropped_blocks)
}

num_precincts <- nrow(county_precincts)
precinct_blocks_list <- mapply(assign_blocks_to_precinct, seq_len(num_precincts), SIMPLIFY = FALSE)
precinct_blocks <- do.call(rbind, precinct_blocks_list)

cat(sprintf(
  "Assigned %d blocks across %d precincts.\n",
  nrow(precinct_blocks), num_precincts
))
