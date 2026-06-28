library(sf)
library(data.table)
library(here)
library(dplyr)
library(ggplot2)

setwd(here())
source("R/result_analysis/utility_functions/shape_extraction_functions.r")
source("R/result_analysis/Extraction_configs/Monongalia_County_WV.r")
source("R/result_analysis/extract_precincts.r")

blocks_for_73 <- block_precinct_assignment[block_precinct_assignment$Precinct_I == "Monongalia_73", ]

#reprojects coordinate transforms of county precincts and blocks
#keeps the GEOID20
county_precincts_proj <- st_transform(county_precincts, AREA_CRS)
county_blocks_proj <- st_transform(county_blocks, AREA_CRS)
county_blocks_proj <- county_blocks_proj[, c("GEOID20")]

#get total population for each block and merge into county blocks
p3_population_dt <- data.table(p3_population)[
  , .(GEOID20 = sub("^1000000US", "", GEO_ID), total_population)
]
county_blocks_proj <- merge(county_blocks_proj, p3_population_dt, by = "GEOID20")


sf_use_s2(FALSE)
# it computes the geometric intersection of every block against every precinct, 
# producing one row per block/precinct pair that actually overlaps in space 
all_block_precinct_overlaps <- st_intersection(county_blocks_proj, county_precincts_proj)
#compute the area of each overlap
all_block_precinct_overlaps$overlap_area <- as.numeric(st_area(all_block_precinct_overlaps$geometry))

#select the blocks that intersect precinct 73
geoids_touching_73 <- all_block_precinct_overlaps %>%
  filter(Precinct_I == "Monongalia_73") %>%
  pull(GEOID20)

#and the precincts that these blocks intersect
blocks_touching_73 <- all_block_precinct_overlaps %>%
  filter(GEOID20 %in% geoids_touching_73) 


#map the blocks touching Monongalia_73, colored by which precinct each
#overlap piece belongs to, with the boundaries of those same precincts
#(from county_precincts_proj, already in AREA_CRS) drawn on top
precincts_touching_73 <- county_precincts_proj %>%
  filter(Precinct_I %in% unique(blocks_touching_73$Precinct_I))

precinct_73_outline <- precincts_touching_73 %>%
  filter(Precinct_I == "Monongalia_73")

precinct_73_map <- ggplot() +
  geom_sf(data = blocks_touching_73, aes(fill = GEOID20), alpha = 0.6) +
  geom_sf(data = precincts_touching_73, fill = NA, color = "black", linewidth = 0.8) +
  geom_sf(data = precinct_73_outline, fill = NA, color = "red", linewidth = 1) +
  geom_sf_text(data = precincts_touching_73, aes(label = Precinct_I)) +
  labs(title = "Blocks touching Monongalia_73, and the precincts those blocks also touch")

precinct_analysis_output_folder <- file.path("precinct_analysis_outputs", LOCATION)
if (!file.exists(file.path(here(), precinct_analysis_output_folder))) {
  dir.create(file.path(here(), precinct_analysis_output_folder), recursive = TRUE)
}

ggsave(
  file.path(precinct_analysis_output_folder, "precinct_73_block_overlaps.png"),
  precinct_73_map, width = 8, height = 6
)

########
# Compare county_precincts (the state-extracted shapefile used above)
# against the county-provided precinct layer pulled from the county's
# ArcGIS Online voting district map
# (datasets/precincts/Monongalia_County_WV/Monongalia_County_Precincts.shp)
########

county_provided_precincts <- st_read(
  "datasets/precincts/Monongalia_County_WV/Monongalia_County_Precincts.shp"
)
county_provided_precincts$Precinct_I <- paste0(
  "Monongalia_", trimws(county_provided_precincts$Precinct)
)
county_provided_precincts_proj <- st_transform(county_provided_precincts, AREA_CRS)

#precincts present in only one source
state_only_precincts <- setdiff(county_precincts_proj$Precinct_I, county_provided_precincts_proj$Precinct_I)
county_provided_only_precincts <- setdiff(county_provided_precincts_proj$Precinct_I, county_precincts_proj$Precinct_I)

cat("Precincts in the state shapefile but not the county-provided layer:\n")
print(state_only_precincts)
cat("Precincts in the county-provided layer but not the state shapefile:\n")
print(county_provided_only_precincts)

#for precincts present in both sources, compute a percent-overlap metric:
#intersection-over-union, so 100% means the two sources draw the identical
#boundary and 0% means the two shapes share no area at all
matched_precinct_ids <- intersect(county_precincts_proj$Precinct_I, county_provided_precincts_proj$Precinct_I)

precinct_geometry_comparison <- rbindlist(lapply(matched_precinct_ids, function(precinct_id) {
  state_shape <- county_precincts_proj[county_precincts_proj$Precinct_I == precinct_id, ]
  county_shape <- county_provided_precincts_proj[county_provided_precincts_proj$Precinct_I == precinct_id, ]

  intersection_shape <- st_intersection(state_shape, county_shape)
  intersection_area <- if (nrow(intersection_shape) == 0) {
    0
  } else {
    as.numeric(st_area(intersection_shape))
  }

  union_area <- as.numeric(st_area(st_union(st_union(state_shape), st_union(county_shape))))

  data.table(
    Precinct_I = precinct_id,
    percent_overlap = 100 * intersection_area / union_area
  )
}))

precinct_geometry_comparison[order(percent_overlap)]

