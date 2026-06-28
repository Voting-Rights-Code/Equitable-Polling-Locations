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

########
# Constants
########
CRS_PROJECTION <- 4326


###### Step 1: extract and validate the county's precincts#######
county_precincts <- extract_county_precincts(STATE_PRECINCT_SOURCE_FILE, COUNTY_NAME, CRS_PROJECTION)


###currently commented out due to the bug where precinct 73 has no population. see issue 283
#stopifnot(
#  "Precinct count does not match EXPECTED_PRECINCT_COUNT in the config file" =
#    nrow(county_precincts) == EXPECTED_PRECINCT_COUNT
#)

county_precincts <- county_precincts[, c("Precinct_I", "County_Nam", "USER_POLL_")]

names(county_precincts)[names(county_precincts) == "geometry"] <- "precinct_geometry"
st_geometry(county_precincts) <- "precinct_geometry"

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

# write every (block, precinct) pair with more than 5% overlap -- one row
# per precinct a block significantly overlaps, unlike the single
# dominant-precinct assignment above (#283)
overlapping_blocks <- flag_overlapping_blocks(
  county_precincts, county_blocks, p3_population, area_crs = AREA_CRS
)

st_write(
  overlapping_blocks %>% filter(flagged == TRUE),
  file.path(precinct_analysis_output_folder, "flagged_overlapping_blocks.gpkg"), append = FALSE
)

###### Step 5: reconcile county-provided precinct data #######
if (COUNTY_PROVIDES_PRECINCT_DATA) {
  provided_polls <- fread(COUNTY_PROVIDED_PRECINCT_FILE)

  # the source file repeats the "Prec" header once per precinct slot (a
  # polling place can serve several precincts); give each slot a unique
  # name so reshape_county_precincts_long()'s melt() can address them
  precinct_slot_positions <- which(names(provided_polls) == "Prec")
  setnames(
    provided_polls,
    old = precinct_slot_positions,
    new = paste0("Prec_", seq_along(precinct_slot_positions))
  )

  county_precincts_resolved <- reconcile_county_provided_precincts(
    provided_polls,
    precinct_columns = paste0("Prec_", seq_along(precinct_slot_positions)),
    location_name_col = COUNTY_PRECINCT_LOCATION_NAME_COL,
    address_col = COUNTY_PRECINCT_ADDRESS_COL,
    county_precincts = county_precincts,
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
    county_precincts, precinct_population,
    by = "Precinct_I", sort = FALSE
  )
  county_precincts_resolved <- county_precincts_resolved[
    county_precincts_resolved$total_population > 0,
  ]
  county_precincts_resolved$total_population <- NULL
}
