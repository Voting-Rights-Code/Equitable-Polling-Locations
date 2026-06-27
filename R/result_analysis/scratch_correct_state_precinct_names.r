library(sf)
library(data.table)
library(here)

setwd(here())
source("R/result_analysis/utility_functions/shape_extraction_functions.r")
source("R/result_analysis/Extraction_configs/Monongalia_County_WV.r")

########
# Write a corrected copy of the state precinct shapefile: for every precinct
# with a corresponding county-provided polling place, USER_POLL_ is replaced
# with toupper(Polling Place Name) -- the county's name is treated as
# authoritative. The original state shapefile is left untouched; only
# Monongalia's precincts are affected (other counties have no corresponding
# county-provided data to update from).
########

state_precincts <- get_shape_data(STATE_PRECINCT_SOURCE_FILE)

provided_polls <- fread("temp/Precincts_by_Location.csv")
precinct_slot_positions <- which(names(provided_polls) == "Prec")
setnames(
  provided_polls,
  old = precinct_slot_positions,
  new = paste0("Prec_", seq_along(precinct_slot_positions))
)

precincts_long <- reshape_county_precincts_long(
  provided_polls,
  precinct_columns = paste0("Prec_", seq_along(precinct_slot_positions)),
  location_name_col = "Polling Place Name",
  address_col = "Polling Location Address"
)
precincts_long <- add_precinct_id(precincts_long, COUNTY_NAME)

corrected_names <- data.table(st_drop_geometry(state_precincts))[
  , row_number := .I
][
  precincts_long, on = "Precinct_I", USER_POLL_corrected := toupper(`Polling Place Name`)
]

state_precincts$USER_POLL_[corrected_names$row_number[!is.na(corrected_names$USER_POLL_corrected)]] <-
  corrected_names$USER_POLL_corrected[!is.na(corrected_names$USER_POLL_corrected)]

corrected_output_folder <- "datasets/precincts/West_Virginia_20260424_wmA84_corrected"
if (!file.exists(file.path(here(), corrected_output_folder))) {
  dir.create(file.path(here(), corrected_output_folder), recursive = TRUE)
}

st_write(
  state_precincts,
  file.path(corrected_output_folder, "VotingPrecincts_20260424_wmA84_corrected.shp"),
  append = FALSE
)
