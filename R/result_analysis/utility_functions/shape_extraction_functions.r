library(data.table)
library(sf)
library(here)
library(dplyr)
library(ggplot2)

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

# compute the folder-name prefix for the NEXT state-file correction step
# by finding the highest existing v<N> sibling folder under the
# state precinct file's parent directory (if any) and returning v<N+1> 
next_correction_step_prefix <- function(state_precinct_source_file, location) {
  state_folder <- dirname(state_precinct_source_file)
  state_folder_basename <- basename(state_folder)
  precincts_root <- dirname(state_folder)

  version_pattern <- paste0("^", state_folder_basename, "_", location, "_v([0-9]+)_.*$")
  sibling_folders <- list.dirs(precincts_root, full.names = FALSE, recursive = FALSE)
  matching_folders <- sibling_folders[grepl(version_pattern, sibling_folders)]
  existing_versions <- as.integer(sub(version_pattern, "\\1", matching_folders))

  next_version <- ifelse(length(existing_versions) == 0, 1, max(existing_versions) + 1)
  return(paste0(state_folder_basename, "_", location, "_v", next_version))
}

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


# The actual check that county-provided (polling location, precinct) data agrees with
# state data. Error if any (polling location, precinct) pair appears only on one side.
# Treat county provided data as correct and change state to match.
check_poll_precinct_agreement <- function(county_precincts_long, state_precincts,
                                          state_precinct_source_file, location) {

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
    # County_Nam only comes from state_precincts_dt, USER_POLL_ only comes
    # from county_precincts_long -- NA in either marks which side the row
    # didn't originate from. Checking state_USER_POLL_/USER_POLL_'s values
    # here (instead of row-origin columns) would mislabel a real state
    # precinct with a blank name field as "county_only".
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

    mismatches_path <- file.path(precinct_analysis_output_folder, "location_precinct_mismatches.csv")
    fwrite(mismatched_rows, mismatches_path)

    next_step_prefix <- next_correction_step_prefix(state_precinct_source_file, location)

    stop(
      "Found ", nrow(mismatched_rows), " precinct(s) that disagree between ",
      "the state shapefile and the county file. Full list written to ",
      mismatches_path, " -- see its mismatch_source column: 'state_only' means ",
      "the precinct is in the state shapefile but not the county file; ",
      "'county_only' is the reverse; 'name_mismatch' means the precinct is in ",
      "both but state_USER_POLL_ and USER_POLL_ disagree.\n",
      "Check that the COUNTY_PRECINCT_COLUMN_NAMES are correct. Furthermore, ",
      "investigate with the county/state. For each row, fill in:\n",
      "  - USER_POLL_: the correct polling place name.\n",
      "  - resolution_type: one of 'rename' (same precinct, name only), ",
      "'split' (this county precinct is an administrative division of ",
      "an existing state precinct), or 'drop' (this precinct is not ",
      "recognized by the county).\n",
      "  - geometry_source_precinct_I: for 'split' rows only, the ",
      "state provided ",
      "Precinct_I whose geometry this row should reuse. Blank for 'rename' ",
      "and 'drop'.\n",
      "DO NOT remove rows -- a 'drop' decision belongs in resolution_type, ",
      "not in deleting the row.\n",
      "Document the decision in a new script under ",
      "R/result_analysis/WV_state_file_corrections/ named ",
      next_step_prefix, "_fix_precinct_ids.r that calls apply_corrections(), ",
      "then re-run extract_precincts.r."
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
                                           state_precincts, county_name,
                                           state_precinct_source_file, location) {
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
    precincts_long, state_precincts, state_precinct_source_file, location
  )

return(corrected_state_data)
}

# build a (Precinct_I, resolved_polling_location) crosswalk from a reviewed
# mismatches table. One row per as-provided Precinct_I that needed a
# correction; resolved_polling_location is NA where no real destination
# exists. Does not include untouched precincts -- their as-provided
# USER_POLL_ is already correct, so callers should treat "no crosswalk row"
# as "use the as-provided value unchanged."
#
# Splits never contribute their own crosswalk rows. A split's new IDs (e.g.
# a precinct divided into two) are never looked up going forward -- nothing
# points backward at them -- so only the *source* precinct being retired
# needs a crosswalk entry, and that's already exactly what its own "drop"
# row is for. Treating split as a second, independent producer of that same
# entry is what let it silently disagree with the drop row for the same
# Precinct_I; here it only validates, it never emits.
build_precinct_crosswalk <- function(reviewed_corrections) {
  rename_rows <- reviewed_corrections[
    resolution_type == "rename",
    .(Precinct_I = Precinct_I, resolved_polling_location = USER_POLL_)
  ]

  # a "drop" row's own USER_POLL_ is the single source of truth for its
  # crosswalk destination -- blank/NA means genuinely unresolvable (no real
  # destination exists), a filled-in value means the ID is retired but its
  # voters have a known destination (e.g. via a split, validated below).
  drop_rows <- reviewed_corrections[
    resolution_type == "drop",
    .(Precinct_I = Precinct_I,
      resolved_polling_location = fifelse(
        is.na(USER_POLL_) | USER_POLL_ == "", NA_character_, USER_POLL_
      ))
  ]

  unsupported <- reviewed_corrections[
    !(resolution_type %in% c("rename", "split", "drop"))
  ]
  stopifnot(
    "Found a resolution_type this function doesn't support yet (e.g. \
    'merge'). Not implemented -- extend build_precinct_crosswalk() before \
    using it." =
      nrow(unsupported) == 0
  )

  crosswalk <- rbind(rename_rows, drop_rows)

  split_rows <- reviewed_corrections[resolution_type == "split"]
  if (nrow(split_rows) > 0) {
    # every split row targeting the same source precinct must resolve to the
    # same polling location -- a genuine geographic split (different
    # destinations per new ID) needs new geometry this function can't
    # produce, and is out of scope until a real case forces the question.
    destination_counts <- split_rows[
      , .(distinct_destinations = uniqueN(USER_POLL_)),
      by = geometry_source_precinct_I
    ]
    stopifnot(
      "A split's target rows resolve to more than one polling location -- \
      this requires new precinct geometry, which apply_corrections() cannot \
      derive from a duplicate. Needs a human decision, not an automatic \
      split." =
        all(destination_counts$distinct_destinations == 1)
    )

    split_sources <- unique(split_rows[
      , .(Precinct_I = geometry_source_precinct_I,
          split_destination = USER_POLL_)
    ])
    stopifnot(
      "A split's geometry_source_precinct_I has no row of its own in the \
      reviewed corrections -- every split source needs an explicit \
      resolution_type recording where it resolves to, same as any other \
      retired precinct." =
        all(split_sources$Precinct_I %in% crosswalk$Precinct_I)
    )

    matched <- crosswalk[split_sources, on = "Precinct_I"]
    stopifnot(
      "A split source's own recorded destination disagrees with where its \
      split targets resolve -- reconcile which one is correct before this \
      can run." =
        all(matched$resolved_polling_location == matched$split_destination)
    )
  }

  crosswalk
}

# read a human-reviewed location_precinct_mismatches.csv and mechanically
# apply every row's resolution_type to state_precincts. Returns the
# corrected precinct geometry and the crosswalk Step 7 needs -- no
# per-county code required for rename/split/drop.
apply_corrections <- function(state_precincts, mismatches_csv_path,
                              existing_crosswalk_path = NULL) {
  reviewed_corrections <- fread(mismatches_csv_path)
  stopifnot(
    "location_precinct_mismatches.csv has unfilled resolution_type rows -- \
    every row must be reviewed and assigned rename/split/drop before this \
    can run" =
      all(!is.na(reviewed_corrections$resolution_type))
  )

  new_crosswalk <- build_precinct_crosswalk(reviewed_corrections)

  has_existing_crosswalk <- !is.null(existing_crosswalk_path) &&
    file.exists(existing_crosswalk_path)
  if (has_existing_crosswalk) {
    prior_crosswalk <- fread(existing_crosswalk_path)
    crosswalk <- rbind(prior_crosswalk, new_crosswalk)
  } else {
    crosswalk <- new_crosswalk
  }

  # renames: relabel in place, geometry untouched
  rename_targets <- reviewed_corrections[resolution_type == "rename"]
  rename_rows <- match(rename_targets$Precinct_I, state_precincts$Precinct_I)
  stopifnot(
    "Every rename's Precinct_I must exist in state_precincts" =
      all(!is.na(rename_rows))
  )
  state_precincts$USER_POLL_[rename_rows] <- rename_targets$USER_POLL_

  # splits: duplicate the source row once per target, drop the source
  split_targets <- reviewed_corrections[resolution_type == "split"]
  if (nrow(split_targets) > 0) {
    split_source_ids <- unique(split_targets$geometry_source_precinct_I)
    new_rows_list <- lapply(seq_len(nrow(split_targets)), function(i) {
      source_precinct_id <- split_targets$geometry_source_precinct_I[i]
      source_row <- state_precincts[
        state_precincts$Precinct_I == source_precinct_id,
      ]
      stopifnot(
        "A split's geometry_source_precinct_I must exist in state_precincts" =
          nrow(source_row) == 1
      )
      source_row$Precinct_I <- split_targets$Precinct_I[i]
      source_row$USER_POLL_ <- split_targets$USER_POLL_[i]
      source_row
    })
    state_precincts <- state_precincts[
      !(state_precincts$Precinct_I %in% split_source_ids),
    ]
    state_precincts <- rbind(state_precincts, do.call(rbind, new_rows_list))
  }

  # drops: remove entirely
  drop_targets <- reviewed_corrections[resolution_type == "drop"]
  state_precincts <- state_precincts[
    !(state_precincts$Precinct_I %in% drop_targets$Precinct_I),
  ]

  list(state_precincts = state_precincts, crosswalk = crosswalk)
}

# intersect every census block against every
# precinct, and report each overlap's
# area and the percent of the block's area that overlap leaves outside the
# precinct. One row per (block, precinct) pair that overlaps at all -- a
# block touching 3 precincts produces 3 rows. 
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

# associate each census block with its dominant
# (largest-overlap) precinct.
# also report the percent of the block's area outside that precinct, and a
# flag for blocks whose dominant precinct holds between 50% and 90% of the
# block.
assign_block_to_dominant_precinct <- function(block_precinct_intersection) {

  # keep only each block's dominant (largest-overlap) precinct(s).
  # with_ties = TRUE deliberately keeps every tied precinct, not just one
  # in the case of duplicate precinct geometries needed to reconcile
  #state and county data.
  block_precinct_intersection <- block_precinct_intersection %>%
              group_by(GEOID20) %>%
              slice_max(overlap_area, n = 1, with_ties = TRUE) %>%
              ungroup()

  # flag blocks whose dominant precinct holds between 50% and 90% of the block
  block_precinct_intersection <- block_precinct_intersection %>%
    mutate(flagged = percent_outside_precinct > 0.1 & percent_outside_precinct < 0.5)
  return(block_precinct_intersection)
}

# Flag every block and precinct that significantly 
# overlaps: one row per (block, precinct) pair where the precinct holds more
# than min_percent_overlap of the block's area. A block with significant
# overlap in 3 precincts produces 3 rows. 
flag_overlapping_blocks <- function(block_precinct_intersection, min_percent_overlap = 0.05) {

  block_precinct_intersection$percent_overlap <- 1 -
    block_precinct_intersection$percent_outside_precinct

  block_precinct_intersection <- block_precinct_intersection %>% 
    mutate(flagged = percent_outside_precinct > min_percent_overlap & 
    percent_outside_precinct < 1-min_percent_overlap)
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
  populated_blocks <- populated_blocks[total_population > 0]

  # data with polling location coordinates
  # clean to match block precinct assignment
  potential_locations <- fread(potential_locations_file)
  potential_locations[, USER_POLL_ := toupper(Location)]

  # potential_locations file may depend on county data
  # this should already be resolved. If not halt and force resolution
  # This data cleaning can only happen by hand.
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

# human-readable labels for flag_distant_blocks()'s demographic columns, for
# consistent map/legend naming. Mirrors graph_functions.R's
# demographic_legend_dict, extended to this pipeline's column names (e.g.
# total_population instead of population, plus pacific_islander,
# multiple_races, non_hispanic, which that dict doesn't cover).
demo_pop_legend_dict <- c(
  total_population = "Total",
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

# build a county-level map of census blocks by distance to their assigned
# polling location, with precinct boundaries drawn on top for context.
# Two modes, chosen by demo_pop:
# - demo_pop = NULL: choropleth. Blocks under distance_threshold_m are
#   neutral gray; blocks at or over it are red, graduated by distance_m.
# - demo_pop = a demographic column name (e.g. "total_population", "white"):
#   dot mode, mirroring make_demo_dist_map() in map_functions.R. Only
#   flagged (over-threshold) blocks get a dot, centered on the block's
#   centroid, sized by that demographic's population and colored by
#   distance_m.
# In both modes, blocks with no computed distance (unpopulated, or
# otherwise excluded upstream from flag_distant_blocks -- see #283) get a
# distinct "no data" fill.
make_demo_distance_heat_map <- function(
    block_shapes, distance_flagged_blocks, precinct_shapes, demo_pop,
    distance_threshold_m = DISTANCE_FLAG_THRESHOLD_M, location = LOCATION,
    crs_projection = CRS_PROJECTION) {
  # reproject to a plain lat/lon CRS so the graticule comes out
  # horizontal/vertical
  block_shapes <- st_transform(block_shapes, crs_projection)
  precinct_shapes <- st_transform(precinct_shapes, crs_projection)

  #select relevant columns
  distance_columns <- c("id_orig", "distance_m", "flagged_distance", demo_pop)
  block_distances <- merge(
    block_shapes[, c("GEOID20", "INTPTLAT20", "INTPTLON20", "block_geometry")],
    distance_flagged_blocks[, distance_columns, with = FALSE],
    by.x = "GEOID20", by.y = "id_orig", all.x = TRUE
  )

  #select different subgroups for map
  is_flagged <- block_distances$flagged_distance
  no_population_blocks <- block_distances[is.na(block_distances$distance_m), ]
  under_threshold_blocks <- block_distances[!is.na(is_flagged) & !is_flagged, ]
  over_threshold_blocks <- block_distances[!is.na(is_flagged) & is_flagged, ]

  distance_threshold <- round(distance_threshold_m / 1609.34, 1)
  demo_pop_label <- if (is.null(demo_pop)) {
    NULL
  } else {
    demo_pop_legend_dict[[demo_pop]]
  }
  title_str <- gsub(
    "_", " ",
    paste(
      location, "driving distance to assigned polling location", demo_pop_label
    )
  )
  # gray indicates no population block
  caption_str <- if (is.null(demo_pop)) {
    paste0(
      "White = under ", distance_threshold,
      " mi threshold; Gray = no population"
    )
  } else {
    "White = populated block; Gray = no population"
  }

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

  if (is.null(demo_pop)) {
    heat_map <- heat_map +
      geom_sf(
        data = over_threshold_blocks, aes(fill = distance_m),
        color = "grey60", linewidth = 0.1
      ) +
      scale_fill_gradient(
        low = "#fcbba1", high = "#67000d", name = "Distance (m)"
      )
  } else {
    # dot mode: draw flagged blocks as plain context polygons, then place a
    # dot at each flagged block's centroid, sized by demo_pop's population
    # and colored by distance_m -- mirrors make_demo_dist_map() in
    # map_functions.R.
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
          size = .data[[demo_pop]], color = distance_m
        )
      ) +
      scale_color_gradient(
        low = "#fcbba1", high = "#67000d", name = "Distance (m)"
      ) +
      labs(size = paste(demo_pop_label, 'population'))
  }

  heat_map <- heat_map +
    geom_sf(
      data = precinct_shapes, fill = NA, color = "black", linewidth = 0.4
    ) +
    labs(title = title_str, caption = caption_str) +
    xlab("") + ylab("") +
    theme_minimal()

  file_name <- paste(c(demo_pop, "distance_heat_map.png"), collapse = "_")
  distance_heat_map_path <- file.path(
    precinct_analysis_output_folder, file_name
  )
  ggsave(distance_heat_map_path, heat_map, width = 10, height = 8)

  return()
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
