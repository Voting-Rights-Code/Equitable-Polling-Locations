library(sf)
library(data.table)
library(here)

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

args <- commandArgs(trailingOnly = TRUE)
if (length(args) != 1) {
  stop("Must enter exactly one config file")
} else {
  config_path <- paste0("R/result_analysis/Extraction_configs/", args[1])
  source(config_path)
}

###
# For inline testing only
###
# source("R/result_analysis/Extraction_configs/Monongalia_County_WV.r")

########
# Constants
########
CRS_PROJECTION <- 4326


###### Step 1: extract and validate the county's precincts#######
county_precincts <- extract_county_precincts(PRECINCT_SOURCE_FILE, COUNTY_NAME, CRS_PROJECTION)

stopifnot(
  "Precinct count does not match EXPECTED_PRECINCT_COUNT in the config file" =
    nrow(county_precincts) == EXPECTED_PRECINCT_COUNT
)

#cat(sprintf("Extracted %d precincts into memory.\n", nrow(county_precincts)))

###### Step 2: verify precincts decompose into census blocks #######
county_blocks <- get_shape_data(
  file.path(TIGER_FOLDER, LOCATION, paste0(BLOCK_GEOMETRY_FILES, ".shp")),
  CRS_PROJECTION
)

#cat(sprintf("Read %d census blocks into memory.\n", nrow(county_blocks)))

# assign the blocks intersecting a single precinct, tagged with that
# precinct's id, for combining across all precincts below
assign_blocks_to_precinct <- function(precinct_index) {
  precinct_row <- county_precincts[precinct_index, ]

  intersecting_blocks <- get_shapes_in_boundary(precinct_row, county_blocks, TRUE)
  cropped_blocks <- crop_to_boundary(precinct_row, intersecting_blocks)
  cropped_blocks$Precinct_I <- precinct_row$Precinct_I
  return(cropped_blocks)
}

num_precincts <- nrow(county_precincts)
precinct_blocks_list <- mapply(assign_blocks_to_precinct, seq_len(num_precincts), SIMPLIFY = FALSE)
precinct_blocks <- do.call(rbind, precinct_blocks_list)

cat(sprintf(
  "Assigned %d blocks across %d precincts.\n",
  nrow(precinct_blocks), num_precincts
))

# area calculations need a planar CRS in linear units, not EPSG:4326's
# geographic degrees. Reprojecting (rather than re-enabling sf_use_s2(), the
# other option) avoids both the missing lwgeom package and S2's stricter
# validity rules rejecting some of crop_to_boundary()'s GEOS-computed,
# self-touching block-union geometries as invalid. EPSG:5070 (NAD83 / Conus
# Albers) is the standard equal-area CRS for US census-derived area work.
AREA_CRS <- 5070
county_precincts_proj <- st_transform(county_precincts, AREA_CRS)
precinct_blocks_proj <- st_transform(precinct_blocks, AREA_CRS)

# compute the symmetric-difference area between a precinct and the union of
# its assigned blocks, as a ratio of the assigned blocks' own area. The
# blocks' area (not the precinct's) is the right denominator: any one block
# is typically a small fraction of a precinct's area, so a block straddling
# a precinct boundary would barely move a precinct-area-denominated ratio
# even though it is exactly the kind of split this check needs to catch.
compute_precinct_block_difference <- function(precinct_index) {
  precinct_row <- county_precincts_proj[precinct_index, ]
  assigned_blocks <- precinct_blocks_proj[precinct_blocks_proj$Precinct_I == precinct_row$Precinct_I, ]

  assigned_union <- st_union(assigned_blocks$geometry)
  sym_diff <- st_sym_difference(assigned_union, precinct_row$geometry)

  blocks_area <- st_area(assigned_union)
  sym_diff_area <- st_area(sym_diff)

  data.table(
    Precinct_I = precinct_row$Precinct_I,
    blocks_area = blocks_area,
    sym_diff_area = sym_diff_area,
    ratio = sym_diff_area / blocks_area
  )
}

verification_rows <- mapply(compute_precinct_block_difference, seq_len(num_precincts), SIMPLIFY = FALSE)
verification_table <- rbindlist(verification_rows)

fwrite(verification_table, "/tmp/precinct_block_verification.csv")

cat(sprintf(
  "Wrote %d-row precinct/block verification table to /tmp/precinct_block_verification.csv\n",
  nrow(verification_table)
))
