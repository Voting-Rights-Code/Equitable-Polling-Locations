library(sf)
library(data.table)
library(here)

setwd(here())
source("R/result_analysis/Extraction_configs/Monongalia_County_WV.r")

########
# Step v1 of the WV statewide precinct shapefile's version history.
#
# This is a one-time, dated correction record,
# -- it documents exactly what a human decided and why, for the indicated
# state file vintage "VotingPrecincts_20260424_wmA84".
#
# Corrections below were determined by running extract_precincts.r against
# the stable West_Virginia_20260424_wmA84 path, which halted at
# check_poll_precinct_agreement(), which wrote location_precinct_mismatches.csv
# listing every (Precinct_I, polling location) pair that disagrees between the
# state shapefile and the county file (see its mismatch_source column).
########

########
# SUMMARY OF CHANGES
# Human review found two distinct kinds of correction:
#  - 3 are pure spelling/wording differences for the same building
#    (Monongalia_16, Monongalia_23/25/36, Monongalia_74).
#  - Monongalia_44 is NOT a spelling difference: the state file assigned it
#    to "Granville Fire Dept Bingo Hall Station 2", a different building
#    than the county-provided "Town of Granville Social Hall".
#  - Confirmed this by confering with Monongalia county
#  - Monongalia_2A and Monongalia_2B are assigned to Morgantown Highschool,
#    This is a county level administrative relabeling of Monongalia_2
#    Both rows should inherit the geometry of Monongali_2, which is dropped
#  - Monongalia_A and Monongalia_B are also non-populated and not assigned
#     a location by the state, and should be dropped.
#
# The rename corrections apply no hardcoded values -- they're a join against
# location_precinct_mismatches.csv (the reviewed record, edited in place).
# The 2/2A/2B split and A/B drop are structural (rows created/removed, not
# just a field updated), which a generic join can't express -- those are
# explicit code below, driven by the Precinct_I values named above.
########

########
# Input:  West_Virginia_20260424_wmA84 (STATE_PRECINCT_SOURCE_FILE)
# Output: West_Virginia_20260424_wmA84_Monongalia_County_WV_v1_reconciliation
#         (this step's own fixed identity, not derived -- see
#         next_correction_step_prefix() in shape_extraction_functions.r for
#         how a *future* step's name gets suggested), mirrored back to the
#         stable West_Virginia_20260424_wmA84 path that
#         STATE_PRECINCT_SOURCE_FILE always points to.
########

RECONCILIATION_OUTPUT_FOLDER <- "datasets/precincts/West_Virginia_20260424_wmA84_Monongalia_County_WV_v1_reconciliation"
precinct_analysis_output_folder <- file.path("precinct_analysis_outputs", LOCATION)
RECONCILIATION_CSV <- file.path(precinct_analysis_output_folder, "location_precinct_mismatches.csv")

# copy every file sharing the state shapefile's basename from source_folder
# into destination_folder (shapefile sidecars: .shp, .shx, .dbf, .prj, .cpg,
# .sbn, .sbx, .shp.xml), creating destination_folder if needed.
copy_shapefile_folder <- function(source_folder, destination_folder) {
  if (!file.exists(file.path(here(), destination_folder))) {
    dir.create(file.path(here(), destination_folder), recursive = TRUE)
  }
  source_files <- list.files(source_folder, full.names = TRUE)
  file.copy(source_files, destination_folder, overwrite = TRUE)
}

########
# Read
########

state_precincts <- st_read(STATE_PRECINCT_SOURCE_FILE)
corrections <- fread(RECONCILIATION_CSV)

########
# Simple renames: same precinct, corrected name (state_USER_POLL_ -> USER_POLL_)
########

name_corrections <- corrections[mismatch_source == "name_mismatch"]
rows <- match(name_corrections$Precinct_I, state_precincts$Precinct_I)
stopifnot("Every name_mismatch Precinct_I must exist in the state file" = all(!is.na(rows)))
stopifnot(
  "State file's current USER_POLL_ no longer matches location_precinct_mismatches.csv's state_USER_POLL_ -- something changed since this file was reviewed; re-review before applying" =
    identical(state_precincts$USER_POLL_[rows], name_corrections$state_USER_POLL_)
)
state_precincts$USER_POLL_[rows] <- name_corrections$USER_POLL_

########
# Monongalia_2 -> Monongalia_2A / Monongalia_2B: county-level administrative
# relabeling of a single state precinct, not two real distinct areas. Both
# new rows inherit Monongalia_2's geometry; Monongalia_2 itself is dropped,
# since the county never reports a plain "2".
########

precinct_2_row <- state_precincts[state_precincts$Precinct_I == "Monongalia_2", ]
stopifnot("Expected exactly one Monongalia_2 row before the 2A/2B split" = nrow(precinct_2_row) == 1)

split_targets <- corrections[Precinct_I %in% c("Monongalia_2A", "Monongalia_2B")]
stopifnot(
  "Expected exactly Monongalia_2A and Monongalia_2B as the 2-split targets" =
    identical(sort(split_targets$Precinct_I), c("Monongalia_2A", "Monongalia_2B"))
)

precinct_2a_row <- precinct_2_row
precinct_2a_row$Precinct_I <- "Monongalia_2A"
precinct_2a_row$USER_POLL_ <- split_targets[Precinct_I == "Monongalia_2A", USER_POLL_]

precinct_2b_row <- precinct_2_row
precinct_2b_row$Precinct_I <- "Monongalia_2B"
precinct_2b_row$USER_POLL_ <- split_targets[Precinct_I == "Monongalia_2B", USER_POLL_]

########
# Monongalia_A / Monongalia_B: non-populated, never assigned a location by
# the state, and not referenced by the county at all -- dropped entirely.
########

state_precincts <- state_precincts[
  !(state_precincts$Precinct_I %in% c("Monongalia_2", "Monongalia_A", "Monongalia_B")),
]
state_precincts <- rbind(state_precincts, precinct_2a_row, precinct_2b_row)

########
# Write the reconciled output, then mirror it to the stable path
########

state_precincts_folder <- dirname(STATE_PRECINCT_SOURCE_FILE)
copy_shapefile_folder(state_precincts_folder, RECONCILIATION_OUTPUT_FOLDER)
st_write(
  state_precincts,
  file.path(RECONCILIATION_OUTPUT_FOLDER, basename(STATE_PRECINCT_SOURCE_FILE)),
  append = FALSE
)

copy_shapefile_folder(RECONCILIATION_OUTPUT_FOLDER, state_precincts_folder)
