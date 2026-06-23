library(data.table)
library(sf)
library(here)

######## Set constants########
TIGER_FOLDER <- "datasets/census/tiger"
REDISTRICTING_FOLDER <- "datasets/census/redistricting"
DEMO_BG_FOLDER <- "block group demographics"

###### Functions#######

# read a shapefile from an explicit path and reproject it
get_shape_data <- function(shape_file_path, crs_projection) {
  shape_data <- st_read(shape_file_path)
  shape_data <- st_transform(shape_data, crs_projection)
  return(shape_data)
}

# select a county's precincts from a statewide precinct shapefile, by county
# name. This is custom built for the WV precinct shapefile and may need
# generalization.
extract_county_precincts <- function(precinct_source_file, county_name,
                                     crs_projection) {
  statewide_precincts <- get_shape_data(
    precinct_source_file,
    crs_projection
  )
  county_precincts <- statewide_precincts[
    which(statewide_precincts$County_Nam == county_name),
  ]
  return(county_precincts)
}

# select intersecting or contained shape data from a county, given a boundary
get_shapes_in_boundary <- function(boundary_shape_data, county_shape_data,
                                   intersection_flag) {
  # make data planar. Otherwise the following line throws an error
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

# given a county's precincts, its TIGER census block shapes, and raw P3
# (Total Population 18 Years and Over) redistricting data, return one row
# per block with positive population: its dominant (largest-overlap)
# precinct, the percent of the block's area outside that precinct, and a
# flag for blocks whose dominant precinct holds between 50% and 90% of the
# block (percent_outside_precinct between 0.1 and 0.5).
#
# p3_population must have columns GEO_ID (the "1000000US" + 15-digit block
# id key used by Census redistricting files) and total_population (the
# P3_001N column).
verify_block_precinct_decomposition <- function(county_precincts, county_blocks,
                                                p3_population, area_crs = 5070) {
  county_precincts <- st_transform(county_precincts, area_crs)
  county_blocks <- st_transform(county_blocks, area_crs)
  county_blocks <- county_blocks[, c("GEOID20", "INTPTLAT20", "INTPTLON20")]

  # merge in total population and drop blocks with none
  p3_population <- data.table(p3_population)[
    , .(GEOID20 = sub("^1000000US", "", GEO_ID), total_population)
  ]
  county_blocks <- merge(county_blocks, p3_population, by = "GEOID20")
  county_blocks <- county_blocks[county_blocks$total_population > 0, ]
  county_blocks$block_area <- st_area(county_blocks$geometry)

  # intersect blocks with precincts and compute the percent of each block
  # outside the precinct it overlaps
  block_precinct_intersection <- st_intersection(county_blocks, county_precincts)
  block_precinct_intersection$overlap_area <- st_area(block_precinct_intersection$geometry)

  # drop sliver polygons: GEOS intersecting two polygons that share a long
  # boundary edge produces a vanishingly thin (but technically nonzero-area)
  # polygon along that edge, in addition to any real overlap. These are
  # floating-point noise -- area is consistently under 1 sq m, while real
  # overlaps start in the hundreds of sq m.
  block_precinct_intersection <- block_precinct_intersection[
    as.numeric(block_precinct_intersection$overlap_area) > 1,
  ]
  block_precinct_intersection$percent_outside_precinct <- 1 -
    as.numeric(block_precinct_intersection$overlap_area) /
    as.numeric(block_precinct_intersection$block_area)

  # keep only each block's dominant (largest-overlap) precinct. A block can
  # still show a real (non-floating-point) but negligible secondary overlap
  # with a neighboring precinct it barely touches -- a few sq m of a
  # million-sq-m block, from the two boundary layers not lining up exactly
  # -- and that's not a meaningful split. Without this step, a metric like
  # max(percent_outside_precinct) ends up dominated by whichever such sliver
  # happens to be largest anywhere in the county.
  block_precinct_intersection <- as.data.table(block_precinct_intersection)[
    order(-overlap_area), .SD[1],
    by = GEOID20
  ]

  block_precinct_intersection[
    , flagged := percent_outside_precinct > 0.1 & percent_outside_precinct < 0.5
  ]

  return(block_precinct_intersection)
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
