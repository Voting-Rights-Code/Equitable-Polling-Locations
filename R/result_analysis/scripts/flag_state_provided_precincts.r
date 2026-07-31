#########
# Note to user:
# Run once per (county, state-file
# vintage); re-run only if the state issues a new shapefile.
#########

library(sf)
library(data.table)
library(here)
library(dplyr)

setwd(here())
source("R/result_analysis/utility_functions/city_shape_functions.r")
source("R/result_analysis/utility_functions/precinct_shape_functions.r")

###
# For inline testing only
###
source("R/result_analysis/precinct_configs/Monongalia_County_WV.r")


######
# Step 1: extract the county's data from the state provided
# precinct file. These are the AS-PROVIDED precincts.
######

as_provided_precincts <- extract_county_precincts(
  STATE_PRECINCT_FILE, COUNTY_NAME, CRS_PROJECTION
)
as_provided_precincts <- as_provided_precincts[, c("Precinct_I", "County_Nam", "USER_POLL_")]
names(as_provided_precincts)[names(as_provided_precincts) == "geometry"] <- "precinct_geometry"
st_geometry(as_provided_precincts) <- "precinct_geometry"

######
# Step 2: extract the county's census blocks and population
######

#get county shape data
tiger_file_path <- file.path(TIGER_FOLDER, LOCATION, paste0(BLOCK_GEOMETRY_FILES, ".shp"))
county_blocks <- get_shape_data(tiger_file_path)

#get county demographic data
p3_file_path <- file.path(REDISTRICTING_FOLDER, LOCATION, "DECENNIALPL2020.P3-Data.csv")
p3_population <- fread(
  p3_file_path,
  header = FALSE, skip = 2,
  select = c(1, 3), col.names = c("GEO_ID", "population")
)

########## Set folder for outputs #############
#create output folder
precinct_analysis_output_folder <- file.path("precinct_analysis_outputs", LOCATION)
if (!file.exists(file.path(here(), precinct_analysis_output_folder))) {
  dir.create(file.path(here(), precinct_analysis_output_folder), recursive = TRUE)
}
setwd(file.path(here(), precinct_analysis_output_folder))

######
# Step 3: associate blocks with their dominant state provided precinct.
# Write both the full association table, and the associations with some
# uncertainty (flagged) to file
######

block_precinct_intersection <- compute_block_precinct_overlaps(
  as_provided_precincts, county_blocks, p3_population, AREA_CRS
)

block_precinct_assignment <- assign_block_to_dominant_precinct(block_precinct_intersection)


######
# Step 4: flag every (block, precinct) pair with significant overlap
# Write to file for review against "precincts are composed of blocks" 
# hypothesis review
######

overlapping_blocks <- flag_overlapping_blocks(block_precinct_intersection)


######
# Step 5: flag precincts with zero population
# Write to file to flag for anomalous precinct review
######

precincts_with_zero_population <- flag_unpopulated_precincts(
  as_provided_precincts, block_precinct_assignment
)

######
# Step 6: flag populated blocks with no assigned poll
# Write to file to flag for anomalous precinct review
######

unassigned_populated_blocks <- flag_populated_unassigned_blocks(block_precinct_assignment)

