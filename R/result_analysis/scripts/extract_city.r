library(sf)
library(here)
library(ggplot2)


setwd(here())
source("R/result_analysis/utility_functions/city_shape_functions.r")

######## Set constants########
# global
CRS_PROJECTION <- 4326

P3 <- "DECENNIALPL2020.P3-Data.csv"
P4 <- "DECENNIALPL2020.P4-Data.csv"

#######
# Read in command line arguments
# A config file must be given to get the location-specific constants for the
# extraction to be run: BLOCK_GEOMETRY_FILES, BG_GEOMETRY_FILES,
# LOCATION_BASE, LOCATION_SUP, LOCATION_SUB, CITY_LIMIT_FOLDER,
# CONTAINING_COUNTY, CITY_LIMIT_FILE. To extract a new city, add a new
# config file under R/result_analysis/city_configs/ instead of
# editing this file.
#######

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) {
  stop("Must enter exactly one config file")
} else {
  config_path <- paste0("R/result_analysis/city_configs/", args[1])
  source(config_path)
}

###
# For inline testing only
###
# source("R/result_analysis/city_configs/Savannah_City_of_GA.r")

###### Get shape data#######
county_blocks <- get_shape_data(
  file.path(TIGER_FOLDER, CONTAINING_COUNTY, paste0(BLOCK_GEOMETRY_FILES, ".shp")), CRS_PROJECTION
)
county_bgs <- get_shape_data(
  file.path(TIGER_FOLDER, CONTAINING_COUNTY, paste0(BG_GEOMETRY_FILES, ".shp")), CRS_PROJECTION
)
city_shape <- get_shape_data(
  file.path(TIGER_FOLDER, CONTAINING_COUNTY, CITY_LIMIT_FOLDER, paste0(CITY_LIMIT_FILE, ".shp")), CRS_PROJECTION
)

###### compute intersecting and contained blocks and block groups######
intersecting_blocks <- get_shapes_in_boundary(city_shape, county_blocks, TRUE)
contained_blocks <- get_shapes_in_boundary(city_shape, county_blocks, FALSE)

intersecting_bgs <- get_shapes_in_boundary(city_shape, county_bgs, TRUE)
contained_bgs <- get_shapes_in_boundary(city_shape, county_bgs, FALSE)

##### plot, just to see that city blocks is, indeed what one wants #####
ggplot() +
  geom_sf(data = intersecting_blocks, fill = "red", alpha = .5) +
  geom_sf(data = city_shape, fill = "yellow", alpha = .5) +
  geom_sf(data = contained_blocks, fill = "blue", alpha = .5)
ggsave(paste0(TIGER_FOLDER, "/", CONTAINING_COUNTY, "/", CITY_LIMIT_FOLDER, "/", "block_selection_options.png"))

ggplot() +
  geom_sf(data = intersecting_bgs, fill = "red", alpha = .5) +
  geom_sf(data = city_shape, fill = "yellow", alpha = .5) +
  geom_sf(data = contained_bgs, fill = "blue", alpha = .5)
ggsave(paste0(TIGER_FOLDER, "/", CONTAINING_COUNTY, "/", CITY_LIMIT_FOLDER, "/", "bg_selection_options.png"))

# get dataframe of city_blocks intersecting the city limits and write to file
# st_write(city_blocks, paste0(TIGER_FOLDER, '/', LOCATION, '/',  BLOCK_GEOMETRY_FILES, '.shp'))


#######
# crop intersecting blocks and assign new interior points
#######
cropped_blocks <- crop_to_boundary(city_shape, intersecting_blocks)
cropped_bgs <- crop_to_boundary(city_shape, intersecting_bgs)
# THIS IS A MANUAL CLUDGE TO AVOID A SPECIFIC ERROR.
cropped_bgs$geometry_type <- st_geometry_type(cropped_bgs$geometry, by_geometry = TRUE)
cropped_bgs <- cropped_bgs[cropped_bgs$geometry_type != "GEOMETRYCOLLECTION", ]
cropped_bgs$geometry_type <- NULL

contained_blocks <- crop_to_boundary(city_shape, contained_blocks)
contained_bgs <- crop_to_boundary(city_shape, contained_bgs)

######## write shape data to file #########
write_to_file(cropped_blocks, LOCATION_SUP, BLOCK_GEOMETRY_FILES)
write_to_file(contained_blocks, LOCATION_SUB, BLOCK_GEOMETRY_FILES)

write_to_file(cropped_bgs, LOCATION_SUP, BG_GEOMETRY_FILES)
write_to_file(contained_bgs, LOCATION_SUB, BG_GEOMETRY_FILES)

######## write demo data to file #########
# blocks
subset_and_write_demo_data(cropped_blocks, P3, LOCATION_SUP, FALSE, CONTAINING_COUNTY)
subset_and_write_demo_data(cropped_blocks, P4, LOCATION_SUP, FALSE, CONTAINING_COUNTY)

subset_and_write_demo_data(contained_blocks, P3, LOCATION_SUB, FALSE, CONTAINING_COUNTY)
subset_and_write_demo_data(contained_blocks, P4, LOCATION_SUB, FALSE, CONTAINING_COUNTY)

# block groups
subset_and_write_demo_data(cropped_bgs, P3, LOCATION_SUP, TRUE, CONTAINING_COUNTY)
subset_and_write_demo_data(cropped_bgs, P4, LOCATION_SUP, TRUE, CONTAINING_COUNTY)

subset_and_write_demo_data(contained_bgs, P3, LOCATION_SUB, TRUE, CONTAINING_COUNTY)
subset_and_write_demo_data(contained_bgs, P4, LOCATION_SUB, TRUE, CONTAINING_COUNTY)
