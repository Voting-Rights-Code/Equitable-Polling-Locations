library(data.table)
library(sf)
library(dplyr)
library(ggplot2)

source("R/result_analysis/utility_functions/city_shape_functions.r")
source("R/result_analysis/utility_functions/tableau_theme.R")
source("R/result_analysis/utility_functions/map_functions.R")


######## Constants ########
POLLING_FOLDER <- "datasets/polling"
POTENTIAL_LOCATIONS_SUFFIX <- "_potential_locations.csv"
DRIVING_FOLDER <- "datasets/driving"
DRIVING_DISTANCE_SUFFIX <- "_driving_distances.csv"
AREA_CRS <- 5070
TIGER_CRS <- 4269
######## Path / IO helpers ########

# path to a location's potential-locations CSV
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

# wrap a digit-only id so that a csv reader (e.g. excel) loads it as text
force_text_for_spreadsheet <- function(id_column) {
  paste0('="', id_column, '"')
}

######## Shared: precinct extraction (Step 1 of both flag_state_provided_precincts.r and extract_precincts.r) ########

# extract county's precincts from a statewide precinct shapefile, by county name.
# Note for future projects: This is custom built for the WV precinct shapefile and may need
# generalization.
extract_county_precincts <- function(precinct_source_file, county_name,
                                     crs_projection = TIGER_CRS) {
  #read state data
  statewide_precincts <- get_shape_data(
    precinct_source_file,
    crs_projection
  )

  #select relevant rows
  state_precincts <- statewide_precincts[
    which(statewide_precincts$County_Nam == county_name), ]

  #check that county name is as expected
  if(nrow(state_precincts) == 0){
    stop(paste(county_name, ' not a valid county in state precinct data.'))
  }
  return(state_precincts)
}

######## flag_state_provided_precincts.r: block/precinct assignment & flagging (Steps 3-6) ########

# intersect every census block against every precinct. Report overlap
# area, percent of the block's area outside the precinct.
# One row per (block, precinct) pair that overlap at all -- a
# block touching 3 precincts produces 3 rows.
compute_block_precinct_overlaps <- function(county_precincts,
                county_blocks, p3_population, area_crs = AREA_CRS,
                crs_projection = TIGER_CRS) {

  #transform to an equal-area projection for area calculations.
  #5070 is NAD83 / Conus Albers.
  county_precincts <- st_transform(county_precincts, area_crs)
  county_blocks <- st_transform(county_blocks, area_crs)

  #select desired columns
  county_blocks <- county_blocks[, c("GEOID20", "INTPTLAT20", "INTPTLON20")]

  #merge in population data
  p3_population <- data.table(p3_population)[
    , .(GEOID20 = sub("^1000000US", "", GEO_ID), population)
  ]
  county_blocks <- merge(county_blocks, p3_population, by = "GEOID20")

  #calculate block area in square meters
  county_blocks$block_area <- as.numeric(st_area(county_blocks$geometry))

  #intersect blocks with precincts to measure overlap
  block_precinct_intersection <- st_intersection(county_blocks, county_precincts)
  block_precinct_intersection$overlap_area <- as.numeric(st_area(block_precinct_intersection$geometry))

  #How much of the block is outside of the precinct.
  block_precinct_intersection$percent_outside_precinct <- 1-
    block_precinct_intersection$overlap_area /
    block_precinct_intersection$block_area

  #swap in each block's full shape in place of the precinct-clipped piece
  st_geometry(block_precinct_intersection) <- county_blocks$geometry[
    match(block_precinct_intersection$GEOID20, county_blocks$GEOID20)
  ]

  # return to project's standard projection
  block_precinct_intersection <- st_transform(block_precinct_intersection, crs_projection)

  #check that all blocks are accounted for
  if (length(unique(block_precinct_intersection$GEOID20)) < length(county_blocks$GEOID20)){
    stop(paste('The following blocks do not intersect any precinct: ',
        paste0(setdiff(county_blocks$GEOID20, unique(block_precinct_intersection$GEOID20)),
        collapse = ', ')))
  }
  return(block_precinct_intersection)
}

# associate each census block with its dominant (largest-overlap) precinct.
# flag for blocks whose dominant precinct holds between 50% and 90% of the
# block. One row per block
assign_block_to_dominant_precinct <- function(block_precinct_intersection) {

  # keep only each block's dominant (largest-overlap) precinct(s). No ties.
  block_precinct_intersection <- block_precinct_intersection %>%
              group_by(GEOID20) %>%
              slice_max(overlap_area, n = 1, with_ties = FALSE) %>%
              ungroup()

  # flag blocks whose dominant precinct holds between 50% and 90% of the block
  block_precinct_intersection <- block_precinct_intersection %>%
    mutate(flagged = percent_outside_precinct > 0.1 & percent_outside_precinct < 0.5)

  st_write(
  block_precinct_intersection, "block_precinct_assignment.gpkg", append = FALSE
)

st_write(
  block_precinct_intersection %>% filter(flagged == TRUE),
  "flagged_assigned_blocks.gpkg", append = FALSE
)

  return(block_precinct_intersection)
}

# Flag every block and precinct that significantly
# overlaps: one row per (block, precinct) pair where the precinct holds between
# min_percent_overlap and 1- min_percent_overlap of the block's area. A block with
# significant overlap in 3 precincts produces 3 rows.
flag_overlapping_blocks <- function(block_precinct_intersection, min_percent_overlap = 0.05) {

  #How much of the block is inside of the precinct.
  block_precinct_intersection$percent_in_precinct <- 1-
    block_precinct_intersection$percent_outside_precinct

  #flag blocks with significant overlap
  block_precinct_intersection <- block_precinct_intersection %>%
    mutate(flagged = percent_outside_precinct > min_percent_overlap &
    percent_outside_precinct < 1-min_percent_overlap)

  #write to file
  st_write(
    block_precinct_intersection %>% filter(flagged == TRUE),
    "flagged_overlapping_blocks.gpkg", append = FALSE
  )

  return(block_precinct_intersection)
}

# flag precincts with zero total population, using the raw as-provided
# precinct shapes (not the block-level geometries) so the output geometry
# matches what a human reviewer expects to see. Writes
# flagged_unpopulated_precincts.gpkg.
flag_unpopulated_precincts <- function(as_provided_precincts, block_precinct_assignment) {
  precinct_population <- data.table(st_drop_geometry(block_precinct_assignment))[
    , .(total_population = sum(population), assigned_blocks = .N), by = Precinct_I
  ]

  precincts_with_zero_population <- merge(
    as_provided_precincts, precinct_population,
    by = "Precinct_I", all.x = TRUE, sort = FALSE
  )
  precincts_with_zero_population <- precincts_with_zero_population %>%
    mutate(unpopulated_precinct = is.na(total_population) | total_population == 0)

  #write to file
  st_write(
    precincts_with_zero_population %>% filter(unpopulated_precinct == TRUE),
    "flagged_unpopulated_precincts.gpkg", append = FALSE
  )

  return(precincts_with_zero_population)
}

# flag populated blocks whose dominant precinct has no assigned polling
# location
flag_populated_unassigned_blocks <- function(block_precinct_assignment) {
  unassigned_populated_blocks <- block_precinct_assignment %>%
    mutate(unassigned_populated = population > 0 & (is.na(USER_POLL_) | USER_POLL_ == ""))

  #write to file
  st_write(
    unassigned_populated_blocks %>% filter(unassigned_populated == TRUE),
    "flagged_unassigned_populated_blocks.gpkg", append = FALSE
  )

  return(unassigned_populated_blocks)
}

######## extract_precincts.r: reconcile county-provided precinct data (Step 2) ########

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

# Check that county-provided and state-provided (polling location, precinct)
# pairs agree everywhere. Identifies mismatches, creates a correction
# table documenting mismatches and prompts the user to enter reconciliation
# data. extract_precincts.r applies the reviewed record automatically on its 
# next run, via apply_corrections().
check_poll_precinct_agreement <- function(county_precincts_long, state_precincts,
                                          location = LOCATION, output_folder = precinct_analysis_output_folder) {

  # rename the state's USER_POLL_ to make merged columns clear
  state_precincts_dt <- data.table(st_drop_geometry(state_precincts))
  setnames(state_precincts_dt, "USER_POLL_", "state_USER_POLL_")

  #outer join state and county data by precinct
  comparison_data <- merge(
    state_precincts_dt, county_precincts_long,
    by = "Precinct_I", all = TRUE
  )

  # a pair mismatches if the precinct is missing from either side (NA), or
  # present on both sides but the names disagree
  mismatched_rows <- comparison_data[
    is.na(state_USER_POLL_) | is.na(USER_POLL_) | state_USER_POLL_ != USER_POLL_
  ]

  if (nrow(mismatched_rows) > 0) {
    # Some state_USER_POLL_ entries are legitimately blank. County_Nam is
    # not. Therefore, we use County_Nam (state column) and USER_POLL_ 
    # (containing county data) to identify missing information.
    mismatched_rows[
      , mismatch_source := fcase(
        is.na(County_Nam), "county_only",
        is.na(USER_POLL_), "state_only",
        default = "name_mismatch"
      )
    ]

    mismatched_rows[
      , `:=`(
        resolution_type = NA_character_,
        geometry_source_precinct_I = NA_character_
      )
    ]

    # write mismatches to file.
    # This is a record of reconciliation between the state and the county.
    # version controlled via git-lfs
    mismatches_path <- file.path(output_folder, "location_precinct_mismatches.csv")
    fwrite(mismatched_rows, mismatches_path)

    stop(
      "Found ", nrow(mismatched_rows), " precinct(s) that disagree between the 
      state shapefile and the county file. Full list written to ", 
      mismatches_path, ".\n
      See its mismatch_source column: 'state_only' means the precinct is in the 
      state shapefile but not the county file; 'county_only' is the reverse; 
      'name_mismatch' means the precinct is in both but state_USER_POLL_ and 
      USER_POLL_ disagree.\n
      Check that the COUNTY_PRECINCT_COLUMN_NAMES are correct. Furthermore, 
      investigate with the county/state. For each unreviewed row, fill in:\n
        - USER_POLL_: the correct polling place name.\n
        - resolution_type: one of 'rename' (same precinct, name only), 
            'split' (this county precinct is an administrative division of an 
                    existing state precinct), 
            or 'drop' (this precinct is not recognized by the county).\n
        - geometry_source_precinct_I: for 'split' rows, the state provided 
                Precinct_I whose geometry this row should reuse. 
                Leave blank for 'rename' and 'drop'.\n
      DO NOT remove rows -- a 'drop' decision belongs in resolution_type, not in
      deleting the row.\n
      Re-run extract_precincts.r once every row is filled in -- it applies this 
      file automatically. If 
      R/result_analysis/WV_state_file_corrections/", location, "_reconciliation.r 
      doesn't exist yet, create it (see an existing one for the pattern) to build 
      the polling-location crosswalk from this file; re-run it whenever new rows are 
      added here."
    )
  }

  # if (USER_POLL_, Precinct_I) match in both directions,
  # return the correct state precinct data
  return(state_precincts)
}

# load a county-provided precinct/polling-location CSV, normalize its
# (possibly repeated) precinct slot column names against precinct_column_names,
# and return state_precincts once verified to agree with it.
reconcile_state_precinct_data <- function(precinct_file, precinct_column_names,
                                           location_name_col, address_col,
                                           state_precincts, county_name, location) {
  #read in county provided data
  provided_polls <- fread(precinct_file)

  #validate the columns indicated in the config against columns in provided data
  precinct_column_numbers <- which(names(provided_polls) %in% precinct_column_names)

  county_column_name_count <- c(table(names(provided_polls)[precinct_column_numbers]))
  config_column_name_count <- c(table(precinct_column_names))
  stopifnot(
    "The COUNTY_PRECINCT_COLUMN_NAMES count doesn't match the source file's matching column count" =
      identical(county_column_name_count, config_column_name_count)
  )

  #make the columns names unique and reshape
  unique_precinct_columns <- make.unique(names(provided_polls)[precinct_column_numbers])
  setnames(provided_polls, old = precinct_column_numbers, new = unique_precinct_columns)

  precincts_long <- reshape_county_precincts_long(
    provided_polls, unique_precinct_columns, location_name_col, address_col
  )
  #clean to match state precinct format
  precincts_long <- add_precinct_id(precincts_long, county_name)
  precincts_long <- precincts_long[, USER_POLL_ := toupper(get(location_name_col))]

  #check if polling location, precinct assignmentsmatch. Flag for manual review.
  #County assignments correct. State precinct list correct.
  #If county does not assign a precinct, use state assignment.
  corrected_state_data <- check_poll_precinct_agreement(
    precincts_long, state_precincts, location
  )

return(corrected_state_data)
}

##### one-off WV_state_file_corrections/*.r scripts: apply a human-reviewed correction #####

# block_precinct_assignments.csv is created before the state data is adjusted
# build a (Precinct_I, resolved_polling_location) crosswalk from a reviewed
# mismatches table. One row per state provided Precinct_I that needed a
# correction; resolved_polling_location is NA for precincts that legitimately
# lack destinations.
build_precinct_crosswalk <- function(reviewed_corrections) {
  #check that resolution type has correct entries.
  unsupported <- reviewed_corrections[
    !(resolution_type %in% c("rename", "split", "drop"))]

  if(nrow(unsupported) != 0){
      stop(paste0(unique(unsupported$resolution_type),
      " is not a supported resolution type"))
  }

  # pull out dropped or renamed rows from the corrections data
  # use the name from the (user corrected) USER_POLL_ column
  # unassigned polling locations are kept as NAs
  crosswalk <- reviewed_corrections[ , resolved_polling_location := USER_POLL_
                ][is.na(USER_POLL_) | USER_POLL_ == "",
                resolved_polling_location := NA_character_
                ][resolution_type == "rename" | resolution_type ==  "drop" ,
                .(Precinct_I, resolved_polling_location) ]

  # verify that the rows labeled "split" have the correct data
  split_rows <- reviewed_corrections[resolution_type == "split"]
  if (nrow(split_rows) > 0) {
    # every split row targeting the same source precinct must have the
    # same polling location
    destination_counts <- split_rows[
      , .(distinct_destinations = uniqueN(USER_POLL_)),
      by = geometry_source_precinct_I
    ]
    stopifnot(
      "A split's target rows resolve to more than one polling location." =
        all(destination_counts$distinct_destinations == 1)
    )

    # every split row points to a valid Precinct_I
    split_sources <- unique(split_rows[
      , .(Precinct_I = geometry_source_precinct_I,
          split_destination = USER_POLL_)
    ])
    stopifnot(
      "A split's geometry_source_precinct_I is not a valid precinct_id." =
        all(split_sources$Precinct_I %in% crosswalk$Precinct_I)
    )

    # every split row's destination matches it's assigned Precinct destination
    matched <- crosswalk[split_sources, on = "Precinct_I"]
    stopifnot(
      "A split source's own recorded destination disagrees with where its \
      split targets resolve -- reconcile which one is correct before this \
      can run." =
        all(matched$resolved_polling_location == matched$split_destination)
    )
  }
  return(crosswalk)
}

# apply a human-reviewed correction data's resolution_type to state_precincts.
# check that data entered correctly
apply_corrections <- function(state_precincts, reviewed_corrections) {
  stopifnot(
    "location_precinct_mismatches.csv has unfilled resolution_type rows -- \
    every row must be reviewed and assigned rename/split/drop before this \
    can run" =
      all(!is.na(reviewed_corrections$resolution_type))
  )

  # Check that every renamed or split precinct has an assigned polling location
  rename_split_poll <- reviewed_corrections[resolution_type %in% c("rename", "split"), USER_POLL_]
  stopifnot(
    "reviewed_corrections has a rename/split row with a blank USER_POLL_ -- \
    every rename/split needs a real destination filled in before this can run" =
    all(!is.na(rename_split_poll) & rename_split_poll != "")
  )

  # renames: relabel in place, geometry untouched
  rename_targets <- reviewed_corrections[resolution_type == "rename",
                        .(Precinct_I, USER_POLL_)]
  stopifnot(
    "Every rename's Precinct_I must exist in state_precincts" =
      all(rename_targets$Precinct_I %in% state_precincts$Precinct_I)
  )
  state_precincts <- state_precincts %>%
    left_join(rename_targets, by = "Precinct_I", suffix = c("", ".new")) %>%
    mutate(USER_POLL_ = coalesce(USER_POLL_.new, USER_POLL_)) %>%
    select(-USER_POLL_.new)

  # splits: duplicate the source row once per target, drop the source
  split_targets <- reviewed_corrections[resolution_type == "split",
              .(Precinct_I, geometry_source_precinct_I, USER_POLL_)]

  if (nrow(split_targets) > 0) {
    stopifnot(
      "A split's geometry_source_precinct_I must exist in state_precincts" =
        all(split_targets$geometry_source_precinct_I %in%
        state_precincts$Precinct_I))


    split_sources <- state_precincts %>% select(-USER_POLL_) %>%
            rename(geometry_source_precinct_I = Precinct_I)
    split_rows <- split_sources %>%
            inner_join(split_targets, by = "geometry_source_precinct_I") %>%
      select(-geometry_source_precinct_I)

    state_precincts <- state_precincts %>%
      filter(!Precinct_I %in% split_targets$geometry_source_precinct_I) %>%
      bind_rows(split_rows)
  }

  # drops: remove entirely
  drop_targets <- reviewed_corrections[resolution_type == "drop"]
  state_precincts <- state_precincts[
    !(state_precincts$Precinct_I %in% drop_targets$Precinct_I),
  ]

  return(state_precincts)
}

######## extract_precincts.r: reshape precinct data into *_result format (Steps 3-4) ########
# The precinct matching data and the solver outputs need to have the same
# shape so that various maps can be made using either.

# read block-level P3 (race) and P4 (hispanic) redistricting tables and
# combine them into one row-per-block demographic breakdown.
get_block_demographics <- function(p3_file_path, p4_file_path) {

  # read P3 and P4 data
  # row 1 holds the real census column codes (GEO_ID, NAME, P3_001N, ...) <- keep;
  # row 2 holds long descriptive labels <- drop;
  # data starts at row 3.
  p3_header <- names(fread(p3_file_path, nrows = 0))
  p3_raw <- fread(p3_file_path, header = FALSE, skip = 2, col.names = p3_header)
  p3_demographics <- p3_raw[, .(
    GEO_ID, population = P3_001N, white = P3_003N, black = P3_004N,
    native = P3_005N, asian = P3_006N, pacific_islander = P3_007N,
    other = P3_008N, multiple_races = P3_009N
  )]

  p4_header <- names(fread(p4_file_path, nrows = 0))
  p4_raw <- fread(p4_file_path, header = FALSE, skip = 2, col.names = p4_header)
  p4_demographics <- p4_raw[, .(
    GEO_ID, population_p4 = P4_001N, hispanic = P4_002N,
    non_hispanic = P4_003N
  )]

  # Merge by block to get all desired demographics
  block_demographics <- merge(p3_demographics, p4_demographics, by = "GEO_ID")

  # Check that the populations match (i.e. that the tables are both pulled for the same data)
  stopifnot(
    "P3 and P4 total population disagree for at least one block" =
      all(block_demographics$population == block_demographics$population_p4)
  )

  #clean columns
  block_demographics[, population_p4 := NULL
                ][, GEOID20 := gsub("^1000000US", "", GEO_ID)
                ][, GEO_ID := NULL]

  return(block_demographics)
}

# resolve every block's final polling-place destination by joining the
# block precinct assignment with the crosswalk of manually edited inconsistencies.
resolve_block_destinations <- function(block_precinct_assignment, state_county_crosswalk) {
  #get block precinct assignment, drop geometry
  all_blocks <- data.table(st_drop_geometry(block_precinct_assignment))

  # merge with crosswalk for correct precinct names: if its as-provided
  # Precinct_I has a crosswalk entry, use that
  # entry as-is (including a real NA). Only fall back to the
  # as-provided USER_POLL_ when the precinct never appears in the crosswalk at
  # all, meaning no correction was ever needed.
  resolved <- merge(all_blocks, state_county_crosswalk, by = "Precinct_I", all.x = TRUE, sort = FALSE)
  resolved[ , resolved_destination := USER_POLL_][Precinct_I %in% state_county_crosswalk$Precinct_I,
                          resolved_destination := resolved_polling_location ]

  resolved[, resolved_polling_location := NULL]
  return(resolved)
}

# get driving distances to resolved polling locations
# Stop if there are missing distances.
get_driving_distances <- function(block_precinct_assignment, state_county_crosswalk,
                                driving_distances) {
  #get resolved blocks precinct assignments
  resolved_blocks <- resolve_block_destinations(block_precinct_assignment,
            state_county_crosswalk)

  #merge in driving distances
  distance_blocks <- merge(
    resolved_blocks, driving_distances, by.x = c("GEOID20", "resolved_destination"),
    by.y = c("id_orig", "id_dest_upper"), all.x = TRUE)

  #alert if there are missing distances or times for blocks with associated polling locations
  missing_distances <- distance_blocks[(is.na(distance_m) | is.na(duration_s)) & !(is.na(resolved_destination) | resolved_destination == ''), ]
  if (nrow(missing_distances)>0){
    stop(paste('The following blocks do not have driving distances: ', paste(missing_distances$GEOID20, collapse = ', ')))
  }

  #convert time to minutes
  distance_blocks[, duration_min := duration_s / 60]

  return(distance_blocks)
}

#combine driving and demographic data to get *_result shaped output
result_shaped_output <- function(block_demographics, block_precinct_assignment,
            state_county_crosswalk, driving_distances){

  #get driving distances
  distance_blocks <- get_driving_distances(block_precinct_assignment,
            state_county_crosswalk, driving_distances)

  #merge. drop distance_blocks population (duplicate) first
  distance_blocks[, population := NULL]
  distance_demographic_blocks <- merge( distance_blocks, block_demographics,
    by = "GEOID20")
  
  distance_demographic_blocks[, weighted_dist := population * distance_m]

  setnames(distance_demographic_blocks, "GEOID20", "id_orig")
  output_columns <- c(
    "id_orig", "id_dest", "distance_m", "duration_min", "Precinct_I", "population",
    "white", "black", "native", "asian", "pacific_islander", "other",
    "multiple_races", "hispanic", "non_hispanic", "weighted_dist")
  distance_demographic_blocks <- distance_demographic_blocks[, ..output_columns]

  return(distance_demographic_blocks)
}

######## extract_precincts.r: distance flagging & heat maps (Steps 5-7) ########

# flag blocks whose drive time exceeds duration_threshold_min. Writes
# distance_flagged_blocks_<N>_min.csv.
flag_distant_blocks <- function(distance_demographic_blocks, duration_threshold_min) {

  flagged_data <- copy(distance_demographic_blocks)
  flagged_data[, flagged_distance := duration_min > duration_threshold_min]

  #write to file
  distance_flagged_blocks_path <- paste0(
    "distance_flagged_blocks_", duration_threshold_min, "_min.csv"
  )
  # write a copy with id_orig text-wrapped for spreadsheet display --
  # demographic_blocks itself stays unwrapped since it's merged on GEOID20
  # downstream (Step 6/7 heat maps).
  demographic_blocks_for_csv <- copy(flagged_data)
  demographic_blocks_for_csv[, id_orig := force_text_for_spreadsheet(id_orig)]

  fwrite(demographic_blocks_for_csv, distance_flagged_blocks_path)

  return(flagged_data)
}

# human-readable labels for flag_distant_blocks()'s demographic columns, for
# consistent map/legend naming.
demographic_legend_dict <- c(
  population = "Total",
  white = "White",
  black = "African American",
  native = "First Nations",
  asian = "Asian (not PI)",
  pacific_islander = "Pacific Islander",
  other = "Other",
  multiple_races = "Multiple Races",
  hispanic = "Latine",
  non_hispanic = "Non-Latine"
)

# read the solver-optimized precinct shapefile. Error if data is stale or missing
get_solver_precinct_shapes <- function(solver_precinct_shapefile,
                                       results_file) {
  # check if file missing
  if (!file.exists(solver_precinct_shapefile)) {
    stop(
      "Solver-optimized precinct shapefile not found at ",
      solver_precinct_shapefile,
      ". Run Basic_analysis.r for this county/config to generate it before ",
      "running extract_precincts.r's Step 7."
    )
  }

  # get timestamp of precinct file and the result file it should be derived from
  # error if stale
  shapefile_mtime <- file.info(solver_precinct_shapefile)$mtime
  results_mtime <- file.info(results_file)$mtime
  if (shapefile_mtime < results_mtime) {
    stop(
      solver_precinct_shapefile, " is older than ", results_file, ". ",
      "The solver results have changed since this shapefile was generated -- ",
      "rerun Basic_analysis.r for this county/config before running Step 7."
    )
  }
  return(st_read(solver_precinct_shapefile))
}

# reshape the results from the optimization run to fit the heat maps
# flag distant columns. optimization_results is copied since this is called
# once per duration threshold on the same shared table, and data.table's
# `:=` mutates by reference.
flagged_optimized_distant_blocks <- function(block_shapes, optimization_results, duration_threshold_min) {

  results <- copy(optimization_results)
  #TODO: until the bug where distance_m has data in seconds for certain runs, this
  #is going to be broken. This will be wired through as part of that bug
  results[, duration_min := distance_m / 60]

  #flag
  results[, flagged_distance := duration_min > duration_threshold_min]

  #reshape
  output_columns <- c(
    "id_orig", "id_dest", "distance_m", "duration_min", "population",
    "white", "black", "native", "asian", "pacific_islander", "other",
    "multiple_races", "hispanic", "non_hispanic", "weighted_dist", "flagged_distance"
  )
  results <- results[, ..output_columns]

  #determine which blocks the solver never assigned (zero population, by design)
  all_blocks <- data.table(st_drop_geometry(block_shapes))[, .(GEOID20, population)]

  ####
  # each zero-population block borrows its nearest assigned precinct's
  # id_dest (see build_destination_fallback_precincts())
  ####
  assigned_block_geometries <- block_shapes[block_shapes$GEOID20 %in% results$id_orig, "GEOID20"]
  assigned_block_geometries <- merge(assigned_block_geometries, results[, .(id_orig, id_dest)], by.x = "GEOID20", by.y = "id_orig")
  destination_fallback_precincts <- build_destination_fallback_precincts(assigned_block_geometries)

  unassigned_block_geometries <- block_shapes[!block_shapes$GEOID20 %in% results$id_orig, "GEOID20"]
  nearest <- st_join(unassigned_block_geometries, destination_fallback_precincts, join = st_nearest_feature)
  nearest_dest <- data.table(st_drop_geometry(nearest))[, .(GEOID20, nearest_dest = id_dest)]

  results_full <- merge(all_blocks, results, by.x = "GEOID20", by.y = "id_orig", all.x = TRUE)
  results_full <- merge(results_full, nearest_dest, by = "GEOID20", all.x = TRUE)
  stopifnot(
    "Every solver-skipped block should have a nearest destination fallback -- nearest_dest may be missing rows for some GEOID20" =
      nrow(results_full[is.na(id_dest) & is.na(nearest_dest)]) == 0
  )
  results_full[is.na(id_dest), id_dest := nearest_dest]
  results_full[, nearest_dest := NULL]

  zero_fill_columns <- setdiff(output_columns, c("id_orig", "id_dest", "population", "flagged_distance"))
  results_full[is.na(duration_min), (zero_fill_columns) := 0]
  results_full[, flagged_distance := duration_min > duration_threshold_min]

  setnames(results_full, "GEOID20", "id_orig")
  results_full <- results_full[, ..output_columns]
  results <- results_full

  #write to file
  distance_flagged_blocks_path <- paste0(
    "optimized_distance_flagged_blocks_", duration_threshold_min, "_min.csv"
  )
  # write a copy with id_orig text-wrapped for spreadsheet display -- results
  # itself stays unwrapped since it's merged on GEOID20 downstream (Step 6/7
  # heat maps).
  results_for_csv <- copy(results)
  results_for_csv[, id_orig := force_text_for_spreadsheet(id_orig)]
  fwrite(results_for_csv, distance_flagged_blocks_path)

  return(results)
}

# read a potential-locations CSV and split its combined
# "Lat, Lon" column into two for plotting
get_polling_locations <- function(location) {
  polling_locations <- fread(build_potential_locations_file_path(location))
  lat_lon_column <- polling_locations[["Lat, Lon"]]
  polling_locations[, c("lat", "lon") := tstrsplit(
    lat_lon_column, ", ", fixed = TRUE, type.convert = TRUE
  )]
  return(polling_locations)
}

# build a county-level map of census blocks by drive time to their assigned
# polling location, with precinct boundaries and polling-location points
# drawn on top for context.
# Two modes, chosen by demographic:
# - demographic = NULL: choropleth.
# - demographic = a demographic column name. Only
#   flagged (over-threshold) blocks get a dot
# In both modes, zero-population blocks get a distinct gray fill.
# Blocks with no assigned polling location get a dashed blue outline.
make_demo_distance_heat_map <- function(
    block_shapes, distance_flagged_blocks, precinct_shapes, polling_locations, demographic,
    duration_threshold_min, location = LOCATION,
    crs_projection = TIGER_CRS, map_label = NULL, color_bounds = NULL) {
  # reproject to a plain lat/lon CRS so the graticule comes out
  # horizontal/vertical
  block_shapes <- st_transform(block_shapes, crs_projection)
  precinct_shapes <- st_transform(precinct_shapes, crs_projection)

  #select relevant columns.
  distance_columns <- setdiff(
    c("id_orig", "id_dest", "distance_m", "duration_min", "flagged_distance", demographic),
    "population"
  )
  block_distances <- merge(
    block_shapes[, c("GEOID20", "population", "INTPTLAT20", "INTPTLON20", "block_geometry")],
    distance_flagged_blocks[, distance_columns, with = FALSE],
    by.x = "GEOID20", by.y = "id_orig", all.x = TRUE
  )

  #select different subgroups for map
  is_flagged <- block_distances$flagged_distance
  no_population_blocks <- block_distances[block_distances$population == 0, ]
  under_threshold_blocks <- block_distances[!is_flagged, ]
  over_threshold_blocks <- block_distances[is_flagged, ]
  not_assigned <- block_distances[is.na(block_distances$id_dest), ]

  #title string
  if (is.null(demographic)) {
      demographic_label <- NULL
      title_str <- gsub( "_", " ", paste(location, "choropleth: driving times to", map_label,
                            "polling location"))
  } else {
      demographic_label <- demographic_legend_dict[[demographic]]
      title_str <- gsub( "_", " ", paste(location, "driving distances to", map_label,
                            "polling location:", demographic_label))
  }

  # caption: gray indicates no population block; dashed blue outline indicates no
  # assigned polling location
  caption_str <- paste0( "White = under ", duration_threshold_min,
                        " min threshold; Gray = no population;\n",
                        "Dashed blue outline = no assigned polling location")

  # base layers shared by both modes: no-data/under-threshold context and
  # precinct boundaries.
  heat_map <- ggplot() +
    geom_sf(
      data = no_population_blocks, fill = "grey75", color = "grey60",
      linewidth = 0.1
    ) +
    geom_sf(
      data = under_threshold_blocks, fill = "white", color = "grey60",
      linewidth = 0.1
    )

  if (is.null(demographic)) {
    heat_map <- heat_map +
      geom_sf(
        data = over_threshold_blocks, aes(fill = duration_min),
        color = "grey60", linewidth = 0.1
      ) +
      scale_fill_gradient(
        low = "#fcbba1", high = "#67000d", name = "Duration (min)", limits = color_bounds
      )
  } else {
    # dot mode: place a dot at each flagged block's centroid, sized by demographic's population
    # and colored by duration_min. blocks drawn for context
    over_threshold_blocks$INTPTLON20 <-
      as.numeric(over_threshold_blocks$INTPTLON20)
    over_threshold_blocks$INTPTLAT20 <-
      as.numeric(over_threshold_blocks$INTPTLAT20)

    heat_map <- heat_map +
      geom_sf(
        data = over_threshold_blocks, fill = "white", color = "grey60",
        linewidth = 0.1
      ) +
      geom_point(
        data = over_threshold_blocks,
        aes(
          x = INTPTLON20, y = INTPTLAT20,
          size = .data[[demographic]], color = duration_min
        )
      ) +
      scale_color_gradient(
        low = "#fcbba1", high = "#67000d", name = "Duration (min)", limits = color_bounds
      ) +
      labs(size = paste(demographic_label, 'population'))
  }

  # drawn last among the fill layers so the dashed outline is visible while
  # leaving the fill showing through
  heat_map <- heat_map +
    geom_sf(
      data = not_assigned, fill = NA, color = "blue", linewidth = 2,
      linetype = "dashed"
    )

  heat_map <- heat_map +
    geom_sf(
      data = precinct_shapes, fill = NA, color = "black", linewidth = 0.4
    ) +
    geom_point(
      data = polling_locations, aes(x = lon, y = lat),
      color = MAP_POLL_TYPE_COLORS[["polling"]], shape = MAP_POLL_TYPE_SHAPES[["polling"]]
    ) +
    labs(title = title_str, caption = caption_str) +
    xlab("") + ylab("") +
    theme_minimal()

  #write to file
  file_name <- paste(
    c(paste0(duration_threshold_min, "_min"), demographic, map_label, "distance_heat_map.png"),
    collapse = "_"
  )
  ggsave(file_name, heat_map, width = 10, height = 8)

  return()
}
