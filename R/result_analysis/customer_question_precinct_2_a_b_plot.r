library(sf)
library(here)
library(ggplot2)

setwd(here())
source("R/result_analysis/utility_functions/shape_extraction_functions.r")
source("R/result_analysis/Extraction_configs/Monongalia_County_WV.r")

########
# Constants
########
CRS_PROJECTION <- 4326

county_precincts <- extract_county_precincts(STATE_PRECINCT_STABLE_FILE, COUNTY_NAME, CRS_PROJECTION)
county_precincts <- county_precincts[, c("Precinct_I", "County_Nam", "USER_POLL_")]

# plot Monongalia_2, Monongalia_A, and Monongalia_B from the state shapefile
# so the Morgantown High School precinct split (#268) can be inspected visually
plot_precinct_2_a_b_split <- function(county_precincts, output_path) {
  split_precincts <- county_precincts[
    county_precincts$Precinct_I %in% c("Monongalia_2", "Monongalia_A", "Monongalia_B"),
  ]

  split_plot <- ggplot(split_precincts) +
    geom_sf(aes(fill = Precinct_I), alpha = 0.6) +
    geom_sf_text(aes(label = Precinct_I)) +
    labs(title = "Monongalia precincts 2, A, and B (state shapefile)")

  ggsave(output_path, split_plot, width = 8, height = 6)
}

precinct_analysis_output_folder <- file.path("precinct_analysis_outputs", LOCATION)
if (!file.exists(file.path(here(), precinct_analysis_output_folder))) {
  dir.create(file.path(here(), precinct_analysis_output_folder), recursive = TRUE)
}

plot_precinct_2_a_b_split(
  county_precincts,
  file.path(precinct_analysis_output_folder, "precinct_2_a_b_split.png")
)
