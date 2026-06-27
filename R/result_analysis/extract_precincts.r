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

stopifnot(
  "Precinct count does not match EXPECTED_PRECINCT_COUNT in the config file" =
    nrow(county_precincts) == EXPECTED_PRECINCT_COUNT
)

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
  file.path(precinct_analysis_output_folder, "flagged_blocks.gpkg"), append = FALSE
)

##############Scratch work for #268 name matching##############3
#load the county-provided polling locations
#provided_polls <- fread(COUNTY_PRECINCT_SOURCE_FILE, header = TRUE)
provided_polls <- fread('temp/Precincts_by_Location.csv')

# give each column with name "Prec" a unique name for  melt()
precinct_slot_positions <- which(names(provided_polls) == "Prec")
setnames(
  provided_polls,
  old = precinct_slot_positions,
  new = paste0("Prec_", seq_along(precinct_slot_positions))
)

# reshape from one row per polling place to one row per (location, precinct)
precincts_long <- melt(
  provided_polls,
  id.vars = c("Polling Place Name", "Polling Location Address"),
  measure.vars = paste0("Prec_", seq_along(precinct_slot_positions)),
  value.name = "precinct_number",
  na.rm = TRUE
)
precincts_long <- precincts_long[
          precinct_number != "", ][ , Precinct_I := paste0("Monongalia_", precinct_number)
          ][  , variable:=NULL][ , precinct_number := NULL]


#merge state data into county data

# Manual lookup for polling-place names that differ between the county's file
# and the state shapefile by more than just case (#268). Case-insensitive
# matching (below) covers every other location -- only these need a hardcoded
# override.
polling_place_name_overrides <- data.table(
  `Polling Place Name` = c(
    "BOPARC Senior Recreation Center",
    "St. Mary's Roman Catholic Church",
    "Town of Granville Social Hall"
  ),
  USER_POLL_ = c(
    "BOPARC SENIOR/COMMUNITY CENTER",
    "ST MARY'S CATHOLIC CHURCH",
    "GRANVILLE SOCIAL HALL"
  )
)

precincts_long <- merge(
  precincts_long, polling_place_name_overrides,
  by = "Polling Place Name", all.x = TRUE
)
precincts_long[
  , USER_POLL_ := fifelse(is.na(USER_POLL_), toupper(`Polling Place Name`), USER_POLL_)
]

name_match_check2 <- merge(
  county_precincts, precincts_long,
  by = c("USER_POLL_", "Precinct_I"),
  all.y = TRUE
)

na_rows2 <- name_match_check2[!complete.cases(st_drop_geometry(name_match_check2)), ]

# Monongalia_2/A/B was visually inspected via
# R/result_analysis/scratch_precinct_2_a_b_plot.r (see precinct_analysis_outputs/
# Monongalia_County_WV/precinct_2_a_b_split.png)

#####
# Interim resolution per client feedback on #268 -- see #281. The client
# confirmed Granville Social Hall serves both 44 and 74 (the state shapefile's
# Bingo Hall assignment for 44 is stale). For Morgantown High School's precinct
# 2/A/B split, block-level population data showed A and B both carry zero
# population, so they're dropped outright rather than folding B into 2 -- no
# equity-relevant difference either way, and dropping is simpler. The 44/74
# resolution still awaits the client's own follow-up with the Secretary of
# State, so #281 stays open.
#####
county_precincts_resolved <- county_precincts

# 1. Assign precinct 44 to Granville Social Hall (overrides the state's stale
# Bingo Hall assignment)
county_precincts_resolved$USER_POLL_[
  county_precincts_resolved$Precinct_I == "Monongalia_44"
] <- "GRANVILLE SOCIAL HALL"

# 2. Drop precincts with zero population, per block-level population data in
# block_precinct_assignment (rather than hardcoding which precincts are empty)
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

# Write county_precincts_resolved to a tmp validation fixture for #282 (note:
# Monongalia_73 is missing here due to #283 -- the dominant-block population
# heuristic incorrectly shows it as zero population). Delete this file before
# the milestone closes.
validation_fixture_folder <- file.path(precinct_analysis_output_folder, "tmp")
if (!file.exists(file.path(here(), validation_fixture_folder))) {
  dir.create(file.path(here(), validation_fixture_folder), recursive = TRUE)
}

fwrite(
  st_drop_geometry(county_precincts_resolved),
  file.path(validation_fixture_folder, "issue_282_validation_fixture.csv")
)


