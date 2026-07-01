library(sf)
library(data.table)
library(here)

setwd(here())
source("R/result_analysis/utility_functions/shape_extraction_functions.r")
source("R/result_analysis/Extraction_configs/Monongalia_County_WV.r")

########
# Back up the state precinct shapefile's original names, then correct just
# the 3 polling-location names that #282's reconciliation flagged as
# mismatched against the county-provided file (case/wording differences
# only -- not a Granville/Morgantown-style substantive disagreement, see
# #268, #281). Nothing else in the shapefile changes.
########

original_folder <- "datasets/precincts/West_Virginia_20260424_wmA84"
backup_folder <- "datasets/precincts/West_Virginia_20260424_wmA84_old_names"

if (!file.exists(file.path(here(), backup_folder))) {
  dir.create(file.path(here(), backup_folder), recursive = TRUE)
}

original_files <- list.files(original_folder, full.names = TRUE)
file.copy(original_files, backup_folder, overwrite = TRUE)
file.rename(
  file.path(backup_folder, basename(original_files)),
  file.path(
    backup_folder,
    gsub(
      "VotingPrecincts_20260424_wmA84",
      "VotingPrecincts_20260424_wmA84_old_names",
      basename(original_files)
    )
  )
)

state_precincts <- get_shape_data(STATE_PRECINCT_SOURCE_FILE)

# old USER_POLL_ value -> corrected value (toupper of the matching
# county-provided "Polling Place Name")
name_corrections <- c(
  "BOPARC SENIOR/COMMUNITY CENTER" = "BOPARC SENIOR RECREATION CENTER",
  "ST MARY'S CATHOLIC CHURCH" = "ST. MARY'S ROMAN CATHOLIC CHURCH",
  "GRANVILLE SOCIAL HALL" = "TOWN OF GRANVILLE SOCIAL HALL"
)

for (old_name in names(name_corrections)) {
  state_precincts$USER_POLL_[state_precincts$USER_POLL_ == old_name] <-
    name_corrections[[old_name]]
}

st_write(state_precincts, STATE_PRECINCT_SOURCE_FILE, append = FALSE)
