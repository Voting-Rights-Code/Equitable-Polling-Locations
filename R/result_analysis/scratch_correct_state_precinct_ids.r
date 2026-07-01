library(sf)
library(data.table)
library(here)

setwd(here())
source("R/result_analysis/utility_functions/shape_extraction_functions.r")
source("R/result_analysis/Extraction_configs/Monongalia_County_WV.r")

########
# Back up the state precinct shapefile (post name-correction), then resolve
# the remaining #281 precinct-ID mismatches:
#  - Monongalia_44: reassign to Town of Granville Social Hall (the state's
#    Granville Fire Dept Bingo Hall assignment is stale per the client).
#  - Monongalia_A / Monongalia_B: dropped entirely -- both carry zero
#    population (see block_precinct_assignment), so there's no
#    equity-relevant reason to retain them.
#  - Monongalia_2: per the client, the 2/A/B split is administrative only
#    ("for all intent and purposes it is noted as precinct 2"), and the
#    county's file tracks it as 2A/2B. Duplicated into two rows
#    (Monongalia_2A, Monongalia_2B) with identical geometry/attributes so
#    the state data's Precinct_I matches the county's labeling.
# Nothing else in the shapefile changes.
########

original_folder <- "datasets/precincts/West_Virginia_20260424_wmA84"
backup_folder <- "datasets/precincts/West_Virginia_20260424_wmA84_old_precinct_ids"

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
      "VotingPrecincts_20260424_wmA84_old_precinct_ids",
      basename(original_files)
    )
  )
)

state_precincts <- get_shape_data(STATE_PRECINCT_SOURCE_FILE)

# 1. Reassign precinct 44
state_precincts$USER_POLL_[state_precincts$Precinct_I == "Monongalia_44"] <-
  "TOWN OF GRANVILLE SOCIAL HALL"

# 2. Drop Monongalia_A and Monongalia_B entirely
state_precincts <- state_precincts[
  !(state_precincts$Precinct_I %in% c("Monongalia_A", "Monongalia_B")),
]

# 3. Duplicate Monongalia_2 into Monongalia_2A and Monongalia_2B
precinct_2_row <- state_precincts[state_precincts$Precinct_I == "Monongalia_2", ]
precinct_2a_row <- precinct_2_row
precinct_2a_row$Precinct_I <- "Monongalia_2A"
precinct_2b_row <- precinct_2_row
precinct_2b_row$Precinct_I <- "Monongalia_2B"

state_precincts <- state_precincts[state_precincts$Precinct_I != "Monongalia_2", ]
state_precincts <- rbind(state_precincts, precinct_2a_row, precinct_2b_row)

st_write(state_precincts, STATE_PRECINCT_SOURCE_FILE, append = FALSE)
