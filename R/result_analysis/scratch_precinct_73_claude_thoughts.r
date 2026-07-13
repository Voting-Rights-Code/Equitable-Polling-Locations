library(sf)
library(data.table)
library(here)
library(dplyr)

setwd(here())
source("R/result_analysis/utility_functions/shape_extraction_functions.r")
source("R/result_analysis/Extraction_configs/Monongalia_County_WV.r")

########
# Explore issue #283: assign_block_to_dominant_precinct()'s winner-take-all
# block assignment reports Monongalia_73 as zero population, even though it
# has real area (~621,510 sq m) and serves a real polling location (Skyview
# Elementary School, alongside precincts 64, 68, 71, 72, 75).
#
# This reproduces the block/precinct overlap calculation with ALL overlaps
# kept (not just each block's dominant precinct), so the winner-take-all
# population can be compared against an overlap-area-weighted population for
# Monongalia_73 specifically.
########

CRS_PROJECTION <- 4326

county_precincts <- extract_county_precincts(STATE_PRECINCT_STABLE_FILE, COUNTY_NAME, CRS_PROJECTION)
county_precincts <- county_precincts[, c("Precinct_I", "County_Nam", "USER_POLL_")]

tiger_file_path <- file.path(TIGER_FOLDER, LOCATION, paste0(BLOCK_GEOMETRY_FILES, ".shp"))
county_blocks <- get_shape_data(tiger_file_path)

p3_file_path <- file.path(REDISTRICTING_FOLDER, LOCATION, "DECENNIALPL2020.P3-Data.csv")
p3_population <- fread(
  p3_file_path,
  header = FALSE, skip = 2,
  select = c(1, 3), col.names = c("GEO_ID", "total_population")
)

county_precincts_proj <- st_transform(county_precincts, AREA_CRS)
county_blocks_proj <- st_transform(county_blocks, AREA_CRS)
county_blocks_proj <- county_blocks_proj[, c("GEOID20", "INTPTLAT20", "INTPTLON20")]

p3_population_dt <- data.table(p3_population)[
  , .(GEOID20 = sub("^1000000US", "", GEO_ID), total_population)
]
county_blocks_proj <- merge(county_blocks_proj, p3_population_dt, by = "GEOID20")
county_blocks_proj$block_area <- as.numeric(st_area(county_blocks_proj$geometry))

sf_use_s2(FALSE)
block_precinct_intersection <- st_intersection(county_blocks_proj, county_precincts_proj)
block_precinct_intersection$overlap_area <- as.numeric(st_area(block_precinct_intersection$geometry))
block_precinct_intersection$percent_outside_precinct <- 1 -
  block_precinct_intersection$overlap_area / block_precinct_intersection$block_area

overlap_dt <- data.table(st_drop_geometry(block_precinct_intersection))

# every block that overlaps Monongalia_73 at all, with every precinct that
# also overlaps that same block
blocks_touching_73 <- overlap_dt[Precinct_I == "Monongalia_73", GEOID20]
all_overlaps_for_73_blocks <- overlap_dt[
  GEOID20 %in% blocks_touching_73,
  .(GEOID20, total_population, Precinct_I,
    overlap_area = round(overlap_area),
    pct_in_precinct = round(100 * (1 - percent_outside_precinct), 1))
][order(GEOID20, -overlap_area)]

cat("=== Every precinct overlapping a block that Monongalia_73 also overlaps ===\n")
print(all_overlaps_for_73_blocks, nrows = 50)

# winner-take-all (current behavior in assign_block_to_dominant_precinct)
dominant <- overlap_dt %>%
  group_by(GEOID20) %>%
  slice_max(overlap_area, n = 1, with_ties = FALSE) %>%
  ungroup()
dominant_dt <- data.table(dominant)
winner_take_all_population_73 <- sum(dominant_dt[Precinct_I == "Monongalia_73", total_population])

cat("\nWinner-take-all total population for Monongalia_73:", winner_take_all_population_73, "\n")

# overlap-area-weighted apportionment (proposed alternative from #283)
overlap_dt[, block_total_overlap_area := sum(overlap_area), by = GEOID20]
overlap_dt[, apportioned_population := total_population * overlap_area / block_total_overlap_area]
overlap_weighted_population_73 <- overlap_dt[Precinct_I == "Monongalia_73", sum(apportioned_population)]

cat("Overlap-area-weighted total population for Monongalia_73:", overlap_weighted_population_73, "\n")
