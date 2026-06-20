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

# select intersecting or contained shape data from a county, given a city file
get_shapes_for_city <- function(city_shape_data, county_shape_data, intersection_flag) {
  # make data planar. Otherwise the following line throws an error
  sf_use_s2(FALSE)

  # choose intersecting or contained data
  if (intersection_flag) {
    indices <- st_intersects(city_shape_data, county_shape_data, sparse = TRUE)
  } else {
    indices <- st_contains(city_shape_data, county_shape_data, sparse = TRUE)
  }
  all_indices <- Reduce(union, indices)
  relevant_shapes <- county_shape_data[all_indices, ]
  return(relevant_shapes)
}

# crop the shapes to be in the city limits, and assign new interior points
crop_to_city_lines <- function(city_shape_data, county_shape_data) {
  # crop shapes
  cropped_shapes <- st_intersection(city_shape_data, county_shape_data)

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

write_to_file <- function(shape_data, location_folder, file_name) {
  # check if requisite folder exists, or create it
  shape_folder <- paste0(TIGER_FOLDER, "/", location_folder)
  if (!file.exists(file.path(here(), shape_folder))) {
    dir.create(file.path(here(), shape_folder))
  }

  # write to file
  st_write(shape_data, paste0(shape_folder, "/", file_name, ".shp"), append = FALSE)
}

subset_and_write_demo_data <- function(city_shape_data, demo_type, location, bg_flag) {
  # read county demo data, skipping first header
  if (bg_flag) {
    county_demo_folder <- paste0(REDISTRICTING_FOLDER, "/", CONTAINING_COUNTY, "/", DEMO_BG_FOLDER)
    city_demo_folder <- paste0(REDISTRICTING_FOLDER, "/", location, "/", DEMO_BG_FOLDER)
  } else {
    county_demo_folder <- paste0(REDISTRICTING_FOLDER, "/", CONTAINING_COUNTY)
    city_demo_folder <- paste0(REDISTRICTING_FOLDER, "/", location)
  }
  # get header rows. We will append these later
  headers <- fread(paste0(county_demo_folder, "/", demo_type), nrow = 2)

  # read in county data
  county_demo <- fread(paste0(county_demo_folder, "/", demo_type), skip = 1, header = TRUE)

  # extract prefix from Geography column for merging
  prefix <- sub("(US).*", "\\1", county_demo$Geography[1])

  # get unique elements of city_shape data
  city_ids <- data.table(GEOID20 = city_shape_data$GEOID20)

  # reformat ids for merging
  city_ids[
    , GEOID20 := paste0(prefix, city_ids$GEOID20) # add prefix in
  ][, GEOID20DUP := gsub("\\..*", "", GEOID20)] # remove suffix for merge

  # merge
  city_demo <- merge(city_ids, county_demo, by.x = "GEOID20DUP", by.y = "Geography", how = "left")
  city_demo$GEOID20DUP <- NULL
  # write to file, check if it exists first
  if (!file.exists(file.path(here(), city_demo_folder))) {
    dir.create(file.path(here(), city_demo_folder))
  }

  # replace the names and add header rows before writing
  names(city_demo) <- names(headers)
  city_demo <- rbind(headers, city_demo)
  fwrite(city_demo, paste0(city_demo_folder, "/", demo_type), append = FALSE, col.names = FALSE)
}
