library(data.table)
library(sf)
library(here)
library(dplyr)

######## Set constants########
TIGER_FOLDER <- "datasets/census/tiger"
REDISTRICTING_FOLDER <- "datasets/census/redistricting"
DEMO_BG_FOLDER <- "block group demographics"
POLLING_FOLDER <- "datasets/polling"
POTENTIAL_LOCATIONS_SUFFIX <- "_potential_locations.csv"
DRIVING_FOLDER <- "datasets/driving"
DRIVING_DISTANCE_SUFFIX <- "_driving_distances.csv"


CRS_PROJECTION <- 4326
AREA_CRS <- 5070
###### Functions#######

# read a shapefile from an explicit path and reproject it
get_shape_data <- function(shape_file_path, crs_projection=CRS_PROJECTION) {
  shape_data <- st_read(shape_file_path)
  shape_data <- st_transform(shape_data, crs_projection)
  return(shape_data)
}

# path to a location's potential-locations CSV (the file the solver reads
# polling locations from, and the source generate_driving_distances_cli.py
# geocodes into the driving-distances matrix). Mirrors
# python/utils/utils.py's build_potential_locations_file_path().
build_potential_locations_file_path <- function(location, polling_folder = POLLING_FOLDER,
                                                potential_locations_suffix = POTENTIAL_LOCATIONS_SUFFIX) {
  return(file.path(
    polling_folder, location, paste0(location, potential_locations_suffix)
  ))
}

# path to a location's driving-distances CSV.
build_driving_distances_file_path <- function(location, driving_folder = DRIVING_FOLDER,
                                              driving_distance_suffix = DRIVING_DISTANCE_SUFFIX) {
  return(file.path(
    driving_folder, location, paste0(location, driving_distance_suffix)
  ))
}

#output folder name
precinct_analysis_output_folder <- file.path("precinct_analysis_outputs", LOCATION)
if (!file.exists(file.path(here(), precinct_analysis_output_folder))) {
  dir.create(file.path(here(), precinct_analysis_output_folder), recursive = TRUE)
}


# select a county's precincts from a statewide precinct shapefile, by county
# name. 
# Note for future projects: This is custom built for the WV precinct shapefile and may need
# generalization.
extract_county_precincts <- function(precinct_source_file, county_name,
                                     crs_projection = CRS_PROJECTION) {
  statewide_precincts <- get_shape_data(
    precinct_source_file,
    crs_projection
  )
  state_precincts <- statewide_precincts[
    which(statewide_precincts$County_Nam == county_name),
  ]
  return(state_precincts)
}

# select intersecting or contained shape data from a county, given a boundary
get_shapes_in_boundary <- function(boundary_shape_data, county_shape_data,
                                   intersection_flag) {
  # make data planar. Otherwise the following line throws an error
  #TODO: This is causing issues. Fix before closing issue 267.
  sf_use_s2(FALSE)

  # choose intersecting or contained data
  if (intersection_flag) {
    indices <- st_intersects(boundary_shape_data, county_shape_data,
      sparse = TRUE
    )
  } else {
    indices <- st_contains(boundary_shape_data, county_shape_data,
      sparse = TRUE
    )
  }
  all_indices <- Reduce(union, indices)
  relevant_shapes <- county_shape_data[all_indices, ]
  return(relevant_shapes)
}

# crop the shapes to be within the boundary, and assign new interior points
crop_to_boundary <- function(boundary_shape_data, county_shape_data) {
  # crop shapes
  cropped_shapes <- st_intersection(boundary_shape_data, county_shape_data)

  # in case of multiple connected components make each component unique
  cropped_shapes$GEOID20 <- gsub("X", "", make.names(cropped_shapes$GEOID20, unique = TRUE))

  # create interior point for cropped shapes
  interior_pt <- st_point_on_surface(cropped_shapes)
  # calculate a new INTPTLAT20/INTPTLON20 column
  interior_pt$INTPTLAT20 <- st_coordinates(interior_pt)[, 2]
  interior_pt$INTPTLON20 <- st_coordinates(interior_pt)[, 1]

  # Keep the shape data for joining
  df_shape <- cropped_shapes[c("GEOID20", "geometry")]
  # drop the geometry from the point data for joining
  interior_pt$geometry <- NULL

  # Join the data and remove columns created by intersection
  df <- merge(df_shape, interior_pt, by = "GEOID20", how = left)
  extra_columns <- c("OBJECTID", "SHAPESTAre", "SHAPESTLen")
  df <- df[, !(names(df) %in% extra_columns)]
  return(df)
}


##### reconcile a county-provided precinct/polling-location file
##### against the state-extracted state_precincts #####

# reshape a county-provided precinct/polling-location table from one row per
# polling place (with one or more columns listing the precincts it serves) to
# one row per (location, precinct) pair. Precinct_columns of length 1 works
# too -- melt() just renames that column into precinct_number.
reshape_county_precincts_long <- function(county_provided_data, precinct_columns,
                                          location_name_col, address_col) {
  precincts_long <- melt(
    county_provided_data,
    id.vars = c(location_name_col, address_col),
    measure.vars = precinct_columns,
    value.name = "precinct_number",
    na.rm = TRUE
  )
  precincts_long <- precincts_long[precinct_number != ""]
  precincts_long[, variable := NULL]
  return(precincts_long)
}

# build a Precinct_I-style key matching the state shapefile's
# <county_name>_<precinct number> convention.
add_precinct_id <- function(precincts_long, county_name) {
  precincts_long[, Precinct_I := paste0(county_name, "_", precinct_number)]
  precincts_long[, precinct_number := NULL]
  return(precincts_long)
}

# case-insensitively match each county-provided location name against the
# state shapefile's USER_POLL_ naming. Name mismatches create a 
# stop()ping error. Resolving requires either
# editing the state source file or confirming a data with the county.
# Treat county provided data as correct and change state to match.
match_location_names <- function(precincts_long, state_precincts, location_name_col) {
  state_names <- unique(state_precincts$USER_POLL_)
  precincts_long[, USER_POLL_ := toupper(get(location_name_col))]

  unmatched_names <- unique(
    precincts_long[[location_name_col]][!(precincts_long$USER_POLL_ %in% state_names)]
  )

  if (length(unmatched_names) > 0) {
    stop(
      "The following polling location name(s) from the county-provided file ",
      "do not match (case-insensitively) any polling location name in the ",
      "state precinct shapefile: ", paste(unmatched_names, collapse = ", "),
      ". Edit these names directly in the state provided source file so ",
      "they match the county's naming, in all caps then re-run."
    )
  }

  return(precincts_long)
}

# check that county-provided precinct data agrees with state_precincts data by
# merging along (location name, Precinct_I). Error if any precinct fails to match on 
# both sides. A mismatch indicates ambiguity about which precinct a location 
# serves; that needs a human-confirmed resolution.
# Treat county provided data as correct and change state to match.
check_precinct_id_agreement <- function(precincts_long, state_precincts) {
  merged <- merge(
    data.table(st_drop_geometry(state_precincts)), precincts_long,
    by = c("USER_POLL_", "Precinct_I"), all = TRUE
  )

  mismatched_rows <- merged[!complete.cases(merged)]

  if (nrow(mismatched_rows) > 0) {
    # County_Nam only comes from state_precincts, so its absence marks a pair
    # the county reported that's missing from the state shapefile, and vice versa
    pair_label <- sprintf(
      "Precinct_I=%s, USER_POLL_=%s",
      mismatched_rows$Precinct_I, mismatched_rows$USER_POLL_
    )
    state_only_pairs <- pair_label[!is.na(mismatched_rows$County_Nam)]
    county_only_pairs <- pair_label[is.na(mismatched_rows$County_Nam)]
    stop(
      "The following Precinct / Location pairs disagree between the state ",
      "shapefile and the county file:\n",
      "Pairs in the state but not county file: ", paste(state_only_pairs, collapse = "; "), "\n",
      "Pairs in the county but not state file: ", paste(county_only_pairs, collapse = "; "), "\n",
      "Check that the COUNTY_PRECINCT_COLUMN_NAMES are correct. Furthermore, 
      investigate with the county/state and update the state file accordingly."
    )
  }

  # if (USER_POLL_, Precinct_I) match in both directions, 
  # return the correct state precinct data
  return(state_precincts)
}

# reconcile a county-provided precinct/
# polling-location file against state_precincts (state shapefile), erroring
# rather than guessing at any name or precinct-ID mismatch.
reconcile_county_provided_precincts <- function(county_provided_data, precinct_columns,
                                                location_name_col, address_col,
                                                state_precincts, county_name) {
  precincts_long <- reshape_county_precincts_long(
    county_provided_data, precinct_columns, location_name_col, address_col
  )
  precincts_long <- add_precinct_id(precincts_long, county_name)
  precincts_long <- match_location_names(precincts_long, state_precincts, location_name_col)
  check_precinct_id_agreement(precincts_long, state_precincts)
}

# load a county-provided precinct/polling-location CSV, normalize its
# (possibly repeated) precinct slot column names against precinct_column_names,
# and return state_precincts once verified to agree with it.
reconciled_state_precinct_data <- function(precinct_file, precinct_column_names,
                                           location_name_col, address_col,
                                           state_precincts, county_name) {
  provided_polls <- fread(precinct_file)

  precinct_column_numbers <- which(names(provided_polls) %in% precinct_column_names)

  county_column_name_count <- c(table(names(provided_polls)[precinct_column_numbers]))
  config_column_name_count <- c(table(precinct_column_names))
  stopifnot(
    "The COUNTY_PRECINCT_COLUMN_NAMES count doesn't match the source file's matching column count" =
      identical(county_column_name_count, config_column_name_count)
  )

  unique_precinct_columns <- make.unique(names(provided_polls)[precinct_column_numbers])
  setnames(provided_polls, old = precinct_column_numbers, new = unique_precinct_columns)

  reconcile_county_provided_precincts(
    provided_polls,
    precinct_columns = unique_precinct_columns,
    location_name_col = location_name_col,
    address_col = address_col,
    state_precincts = state_precincts,
    county_name = county_name
  )
}

# intersect every census block -- populated or not -- against every
# precinct, using the true (unbuffered) boundary, and report each overlap's
# area and the percent of the block's area that overlap leaves outside the
# precinct. One row per (block, precinct) pair that overlaps at all -- a
# block touching 3 precincts produces 3 rows. Shared by
# assign_block_to_dominant_precinct() and flag_overlapping_blocks().
compute_block_precinct_overlaps <- function(county_precincts, county_blocks,
                                            p3_population, area_crs = AREA_CRS) {

  ####clean precinct and block data ####
  #transform to an equal-area projection for area calculations.
  #5070 is NAD83 / Conus Albers.
  county_precincts <- st_transform(county_precincts, area_crs)
  county_blocks <- st_transform(county_blocks, area_crs)

  #select desired columns
  county_blocks <- county_blocks[, c("GEOID20", "INTPTLAT20", "INTPTLON20")]

  #merge in population data
  p3_population <- data.table(p3_population)[
    , .(GEOID20 = sub("^1000000US", "", GEO_ID), total_population)
  ]
  county_blocks <- merge(county_blocks, p3_population, by = "GEOID20")

  #caluculate block area in square meters
  county_blocks$block_area <- as.numeric(st_area(county_blocks$geometry))

  # intersect blocks with precincts and compute the overlap area and percent overlap
  block_precinct_intersection <- st_intersection(county_blocks, county_precincts)
  block_precinct_intersection$overlap_area <- as.numeric(st_area(block_precinct_intersection$geometry))

  block_precinct_intersection$percent_outside_precinct <- 1-
    block_precinct_intersection$overlap_area /
    block_precinct_intersection$block_area

  return(block_precinct_intersection)
}

# associate each census block -- populated or not -- with its dominant
# (largest-overlap) precinct.
# also report the percent of the block's area outside that precinct, and a
# flag for blocks whose dominant precinct holds between 50% and 90% of the
# block.
#NOTE: Assumes that each precinct is a union of blocks. Otherwise
#the dominant precinct logic does not apply.
assign_block_to_dominant_precinct <- function(county_precincts, county_blocks,
                                          p3_population, area_crs = AREA_CRS) {

  block_precinct_intersection <- compute_block_precinct_overlaps(
    county_precincts, county_blocks, p3_population, area_crs
  )

  # keep only each block's dominant (largest-overlap) precinct.
  block_precinct_intersection <- block_precinct_intersection %>%
              group_by(GEOID20) %>%
              slice_max(overlap_area, n = 1, with_ties = FALSE) %>%
              ungroup()

  # flag blocks whose dominant precinct holds between 50% and 90% of the block
  block_precinct_intersection <- block_precinct_intersection %>%
    mutate(flagged = percent_outside_precinct > 0.1 & percent_outside_precinct < 0.5)
  return(block_precinct_intersection)
}

# unlike assign_block_to_dominant_precinct() (one row per block, its single
# dominant precinct), this keeps every precinct a block significantly
# overlaps: one row per (block, precinct) pair where the precinct holds more
# than min_percent_overlap of the block's area. A block with significant
# overlap in 3 precincts produces 3 rows. See #283.
flag_overlapping_blocks <- function(county_precincts, county_blocks, p3_population,
                                    min_percent_overlap = 0.05, area_crs = AREA_CRS) {

  block_precinct_intersection <- compute_block_precinct_overlaps(
    county_precincts, county_blocks, p3_population, area_crs
  )

  block_precinct_intersection$percent_overlap <- 1 -
    block_precinct_intersection$percent_outside_precinct

  block_precinct_intersection <- block_precinct_intersection %>% 
    mutate(flagged = percent_outside_precinct > 0.05 & 
    percent_outside_precinct < .95)
  return(block_precinct_intersection)
}


# read block-level P3 (race) and P4 (hispanic) redistricting tables and
# combine them into one row-per-block demographic breakdown. Output to 
# mirror the demographic information represented in the *_results.csv 
# solver outputs.
get_block_demographics <- function(p3_file_path, p4_file_path) {
  
  ###Read P3 and P4 data #####
  # row 1 holds the real census column codes (GEO_ID, NAME, P3_001N, ...) <- keep;
  # row 2 holds long descriptive labels <- drop; 
  # data starts at row 3. 
  p3_header <- names(fread(p3_file_path, nrows = 0))
  p3_raw <- fread(p3_file_path, header = FALSE, skip = 2, col.names = p3_header)
  p3_demographics <- p3_raw[, .(
    GEO_ID, total_population = P3_001N, white = P3_003N, black = P3_004N,
    native = P3_005N, asian = P3_006N, pacific_islander = P3_007N,
    other = P3_008N, multiple_races = P3_009N
  )]

  p4_header <- names(fread(p4_file_path, nrows = 0))
  p4_raw <- fread(p4_file_path, header = FALSE, skip = 2, col.names = p4_header)
  p4_demographics <- p4_raw[, .(
    GEO_ID, total_population_p4 = P4_001N, hispanic = P4_002N,
    non_hispanic = P4_003N
  )]

  #### Merge by block to get all desired demographics
  block_demographics <- merge(p3_demographics, p4_demographics, by = "GEO_ID")

  ### Check that the populations match (i.e. that the tables are both pulled for the same data)
  stopifnot(
    "P3 and P4 total population disagree for at least one block" =
      all(block_demographics$total_population == block_demographics$total_population_p4)
  )

  #clean columns
  block_demographics[, total_population_p4 := NULL
                ][, GEOID20 := gsub("^1000000US", "", GEO_ID)
                ][, GEO_ID := NULL]

  return(block_demographics)
}

# join each populated census block to its assigned polling location's
# driving distance, extend with demographic data, and flag blocks whose
# distance exceeds distance_threshold_m. 
flag_distant_blocks <- function(block_precinct_assignment, block_demographics,
                                driving_distances_file, potential_locations_file,
                                distance_threshold_m) {
  #drop geometry. Make a data.table 
  #Recall, block_precinct_assignment is based off (potentially modified) state data
  populated_blocks <- data.table(st_drop_geometry(block_precinct_assignment))
  # TODO: revisit once #283 (precinct 73's zero-population bug) is
  # resolved -- some genuinely-populated blocks may currently show
  # total_population == 0 due to that bug, and would be dropped here
  # incorrectly.
  populated_blocks <- populated_blocks[total_population > 0]

  # data with polling location coordinates
  # clean to match block precinct assignment
  potential_locations <- fread(potential_locations_file)
  potential_locations[, USER_POLL_ := toupper(Location)]

  # At this point USER_POLL_ in block assignment and potential_locations.csv's 
  # Location columns should match (Step 5)
  # If they don't error message flahs that they are out of sync.
  resolved_blocks <- merge(
    populated_blocks, potential_locations[, .(USER_POLL_, Location)],
    by = "USER_POLL_"
  )
  stopifnot(
    "Populated blocks' USER_POLL_ and potential_locations.csv's Location did not match one-to-one 
    check if the state provided file still matches data from potential_locations files" =
      nrow(resolved_blocks) == nrow(populated_blocks)
  )

  driving_distances <- fread(driving_distances_file)
  driving_distances[, id_orig := as.character(id_orig)]

  #merge in driving distances
  distance_blocks <- merge(
    resolved_blocks, driving_distances,
    by.x = c("GEOID20", "Location"), by.y = c("id_orig", "id_dest")
  )
  stopifnot(
    "Some resolved blocks' (GEOID20, Location) pair had no matching row in driving_distances_file 
    -- driving_distances_file may be incomplete or out of sync with potential_locations.csv, or vice versa" =
      nrow(distance_blocks) == nrow(resolved_blocks)
  )

  # drop block_demographics' total_population (duplicate) before merging 
  demographic_columns <- setdiff(names(block_demographics), c("GEOID20", "total_population"))
  demographic_blocks <- merge(
    distance_blocks, block_demographics[, c("GEOID20", demographic_columns), with = FALSE],
    by = "GEOID20"
  )
  stopifnot(
    "Some distance-joined blocks' GEOID20 had no matching row in block_demographics 
    -- block_demographics may be incomplete or out of sync with the block/precinct assignment, or vice versa" =
      nrow(demographic_blocks) == nrow(distance_blocks)
  )

  demographic_blocks[, weighted_dist := total_population * distance_m]
  demographic_blocks[, flagged_distance := distance_m > distance_threshold_m]

  setnames(demographic_blocks, c("GEOID20", "Location"), c("id_orig", "id_dest"))
  output_columns <- c(
    "id_orig", "id_dest", "distance_m", "Precinct_I", "total_population",
    "white", "black", "native", "asian", "pacific_islander", "other",
    "multiple_races", "hispanic", "non_hispanic", "weighted_dist", "flagged_distance"
  )
  demographic_blocks <- demographic_blocks[, ..output_columns]

  return(demographic_blocks)
}

write_to_file <- function(shape_data, location_folder, file_name) {
  # check if requisite folder exists, or create it
  shape_folder <- paste0(TIGER_FOLDER, "/", location_folder)
  if (!file.exists(file.path(here(), shape_folder))) {
    dir.create(file.path(here(), shape_folder))
  }

  # write to file
  st_write(shape_data, paste0(shape_folder, "/", file_name, ".shp"), append = FALSE)
}

subset_and_write_demo_data <- function(boundary_shape_data, demo_type, location, bg_flag, containing_county) {
  # read county demo data, skipping first header
  if (bg_flag) {
    county_demo_folder <- paste0(REDISTRICTING_FOLDER, "/", containing_county, "/", DEMO_BG_FOLDER)
    boundary_demo_folder <- paste0(REDISTRICTING_FOLDER, "/", location, "/", DEMO_BG_FOLDER)
  } else {
    county_demo_folder <- paste0(REDISTRICTING_FOLDER, "/", containing_county)
    boundary_demo_folder <- paste0(REDISTRICTING_FOLDER, "/", location)
  }
  # get header rows. We will append these later
  headers <- fread(paste0(county_demo_folder, "/", demo_type), nrow = 2)

  # read in county data
  county_demo <- fread(paste0(county_demo_folder, "/", demo_type), skip = 1, header = TRUE)

  # extract prefix from Geography column for merging
  prefix <- sub("(US).*", "\\1", county_demo$Geography[1])

  # get unique elements of boundary_shape data
  boundary_ids <- data.table(GEOID20 = boundary_shape_data$GEOID20)

  # reformat ids for merging
  boundary_ids[
    , GEOID20 := paste0(prefix, boundary_ids$GEOID20) # add prefix in
  ][, GEOID20DUP := gsub("\\..*", "", GEOID20)] # remove suffix for merge

  # merge
  boundary_demo <- merge(boundary_ids, county_demo, by.x = "GEOID20DUP", by.y = "Geography", how = "left")
  boundary_demo$GEOID20DUP <- NULL
  # write to file, check if it exists first
  if (!file.exists(file.path(here(), boundary_demo_folder))) {
    dir.create(file.path(here(), boundary_demo_folder))
  }

  # replace the names and add header rows before writing
  names(boundary_demo) <- names(headers)
  boundary_demo <- rbind(headers, boundary_demo)
  fwrite(boundary_demo, paste0(boundary_demo_folder, "/", demo_type), append = FALSE, col.names = FALSE)
}
