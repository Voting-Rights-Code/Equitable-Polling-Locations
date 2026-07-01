library(sf)
library(data.table)
library(here)
library(dplyr)

setwd(here())
source("R/result_analysis/utility_functions/shape_extraction_functions.r")

########
# One-off: confirm the COUNTY_PROVIDES_PRECINCT_DATA == TRUE and == FALSE
# branches of extract_precincts.r's Step 5 produce the same
# county_precincts_resolved for Monongalia County, now that the
# zero-population drop runs identically after either branch.
########

run_through_step_5 <- function(config_path) {
  source(config_path)

  state_precincts <- extract_county_precincts(STATE_PRECINCT_SOURCE_FILE, COUNTY_NAME, CRS_PROJECTION)
  state_precincts <- state_precincts[, c("Precinct_I", "County_Nam", "USER_POLL_")]
  names(state_precincts)[names(state_precincts) == "geometry"] <- "precinct_geometry"
  st_geometry(state_precincts) <- "precinct_geometry"

  tiger_file_path <- file.path(TIGER_FOLDER, LOCATION, paste0(BLOCK_GEOMETRY_FILES, ".shp"))
  county_blocks <- get_shape_data(tiger_file_path)

  p3_file_path <- file.path(REDISTRICTING_FOLDER, LOCATION, "DECENNIALPL2020.P3-Data.csv")
  p3_population <- fread(
    p3_file_path,
    header = FALSE, skip = 2,
    select = c(1, 3), col.names = c("GEO_ID", "total_population")
  )

  block_precinct_assignment <- assign_block_to_dominant_precinct(
    state_precincts, county_blocks, p3_population, AREA_CRS
  )
  names(block_precinct_assignment)[names(block_precinct_assignment) == "geometry"] <- "block_geometry"
  st_geometry(block_precinct_assignment) <- "block_geometry"

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

  return(county_precincts_resolved)
}

with_county_data <- run_through_step_5("R/result_analysis/Extraction_configs/Monongalia_County_WV.r")
without_county_data <- run_through_step_5("R/result_analysis/Extraction_configs/Monongalia_County_WV_no_precinct_data.r")

with_county_data <- data.table(st_drop_geometry(with_county_data))[order(Precinct_I)]
without_county_data <- data.table(st_drop_geometry(without_county_data))[order(Precinct_I)]

cat("Rows -- with county data:", nrow(with_county_data), " without:", nrow(without_county_data), "\n")
cat("Identical (geometry dropped):", identical(with_county_data, without_county_data), "\n")
