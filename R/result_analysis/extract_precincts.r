library(sf)
library(data.table)
library(here)
library(dplyr)
library(ggplot2)

setwd(here())
source("R/result_analysis/utility_functions/shape_extraction_functions.r")
source("R/result_analysis/utility_functions/graph_functions.R")
source("R/result_analysis/utility_functions/regression_functions.r")

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
# Create data for time to polling location flagging and heat maps. 

#read in block assignment and manual corrections.
block_precinct_assignment <- st_read(
  file.path(precinct_analysis_output_folder, "block_precinct_assignment.gpkg"))
names(block_precinct_assignment)[names(block_precinct_assignment) == "geometry"] <- "block_geometry"
st_geometry(block_precinct_assignment) <- "block_geometry"


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

#driving distance path
driving_distance_path <- build_driving_distances_file_path(LOCATION)

distance_flagged_blocks_15 <- flag_distant_blocks(
  block_precinct_assignment, state_county_crosswalk, block_demographics,
  driving_distance_path,
  15)

distance_flagged_blocks_20 <- flag_distant_blocks(
  block_precinct_assignment, state_county_crosswalk, block_demographics,
  driving_distance_path,
  20)

solver_distance_flagged_blocks_15 <- flagged_optimized_distant_blocks(
  block_precinct_assignment, OPTIMIZATION_RESULTS, 15
)
solver_distance_flagged_blocks_20 <- flagged_optimized_distant_blocks(
  block_precinct_assignment, OPTIMIZATION_RESULTS, 20
)

# shared color scale across every heat map below to make the maps 
# directly comparable.
# Recall that the _15 and _20 tables are the same, with different flags
flagged_duration_values <- c(
  distance_flagged_blocks_15[flagged_distance == TRUE, duration_min],
  solver_distance_flagged_blocks_15[flagged_distance == TRUE, duration_min]
)

#TODO: the 15 minutes below is hard coded. However, it is hard coded into
# the output file names too. Changing this will need a refactor
duration_color_bounds <- c(15, max(flagged_duration_values, na.rm = TRUE))

###### Step 4: plot county-level distance heat map #######

# Make maps for 15 minutes

# choropleth mode
make_demo_distance_heat_map(
  block_precinct_assignment, distance_flagged_blocks_15,
  precincts_resolved, demo_pop = NULL, 15, color_bounds = duration_color_bounds
)

# dot mode: one map per demographic of interest
make_demo_distance_heat_map(
  block_precinct_assignment, distance_flagged_blocks_15,
  precincts_resolved, demo_pop = "population", 15, color_bounds = duration_color_bounds
)

# Make maps for 20 minutes

# choropleth mode
make_demo_distance_heat_map(
  block_precinct_assignment, distance_flagged_blocks_20,
  precincts_resolved, demo_pop = NULL, 20, color_bounds = duration_color_bounds
)

# dot mode: one map per demographic of interest
make_demo_distance_heat_map(
  block_precinct_assignment, distance_flagged_blocks_20,
  precincts_resolved, demo_pop = "population", 20, color_bounds = duration_color_bounds
)

###### Step 5: plot solver-assignment distance heat map #######

# 15 min
make_demo_distance_heat_map(
  block_precinct_assignment, solver_distance_flagged_blocks_15,
  precincts_resolved, demo_pop = NULL, 15, map_label = "optimized", color_bounds = duration_color_bounds
)
make_demo_distance_heat_map(
  block_precinct_assignment, solver_distance_flagged_blocks_15,
  precincts_resolved, demo_pop = "population", 15, map_label = "optimized", color_bounds = duration_color_bounds
)

# 20 min
make_demo_distance_heat_map(
  block_precinct_assignment, solver_distance_flagged_blocks_20,
  precincts_resolved, demo_pop = NULL, 20, map_label = "optimized", color_bounds = duration_color_bounds
)
make_demo_distance_heat_map(
  block_precinct_assignment, solver_distance_flagged_blocks_20,
  precincts_resolved, demo_pop = "population", 20, map_label = "optimized", color_bounds = duration_color_bounds
)

###### Step 6: plot density vs. distance for actual precinct assignment #######

precinct_density_data <- precinct_bg_density_data(distance_flagged_blocks_15, LOCATION, DEMO_COLS)
precinct_regression_data <- bg_data(precinct_density_data)

solver_density_data <- precinct_bg_density_data(
  solver_distance_flagged_blocks_15, LOCATION, DEMO_COLS, descriptor = "solver_assignment"
)
solver_regression_data <- bg_data(solver_density_data)

# Set y-bound in order to share y-axis scale for regression maps across two different "runs"
# in this case, the solver output, and the optimizer
pooled_density_data <- rbind(precinct_regression_data, solver_regression_data)
shared_density_y_bounds <- compute_density_y_bounds(pooled_density_data, DEMOGRAPHIC_LIST)

#change directories because these maps make different assumptions 
#of where to write
setwd(file.path(here(), precinct_analysis_output_folder))

#plot regression graphs
plot_density_v_distance_bg(
  precinct_regression_data, LOCATION, DEMOGRAPHIC_LIST,
  log_flag = FALSE, driving_flag = TRUE, y_bounds = shared_density_y_bounds
)
plot_density_v_distance_bg(
  solver_regression_data, LOCATION, DEMOGRAPHIC_LIST,
  log_flag = FALSE, driving_flag = TRUE, y_bounds = shared_density_y_bounds
)
setwd(here())
