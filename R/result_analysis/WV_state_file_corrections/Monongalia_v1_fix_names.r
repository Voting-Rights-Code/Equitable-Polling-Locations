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
# the stable West_Virginia_20260424_wmA84 path, which halted at match_location_names(),
# which wrote location_mismatches.csv listing every county-provided polling
# location name with no case-insensitive match in the state file, alongside
# what the state file currently had for that precinct (state_USER_POLL_).
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
#
# This script applies no hardcoded values itself -- the corrections above are
# a description of what a human reviewed and approved directly in
# location_mismatches.csv (edited in place once reviewed). This script is
# just the join that applies whatever that reviewed file says.
########

########
# Input:  West_Virginia_20260424_wmA84 (STATE_PRECINCT_SOURCE_FILE)
# Output: West_Virginia_20260424_wmA84_Monongalia_County_WV_v1_fix_names
#         (this step's own fixed identity, not derived -- see
#         next_correction_step_prefix() in shape_extraction_functions.r for
#         how a *future* step's name gets suggested), mirrored back to the
#         stable West_Virginia_20260424_wmA84 path that
#         STATE_PRECINCT_SOURCE_FILE always points to.
########

NAME_CORRECTION_OUTPUT_FOLDER <- "datasets/precincts/West_Virginia_20260424_wmA84_Monongalia_County_WV_v1_fix_names"
precinct_analysis_output_folder <- file.path("precinct_analysis_outputs", LOCATION)
NAME_MISMATCH_CSV <- file.path(precinct_analysis_output_folder, "location_mismatches.csv")

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
# Read, join in the human-reviewed corrections, write
########

state_precincts <- st_read(STATE_PRECINCT_SOURCE_FILE)

# location_mismatches.csv is the reviewed record: state_USER_POLL_ is what
# was reviewed, USER_POLL_ is the corrected value a human approved (editing
# either column directly in the file, or removing a row that didn't need a
# correction after all).
name_corrections <- fread(NAME_MISMATCH_CSV)

rows <- match(name_corrections$Precinct_I, state_precincts$Precinct_I)
stopifnot("Every Precinct_I in location_mismatches.csv must exist in the state file" = all(!is.na(rows)))
stopifnot(
  "State file's current USER_POLL_ no longer matches location_mismatches.csv's state_USER_POLL_ -- something changed since this file was reviewed; re-review before applying" =
    identical(state_precincts$USER_POLL_[rows], name_corrections$state_USER_POLL_)
)
state_precincts$USER_POLL_[rows] <- name_corrections$USER_POLL_

state_precincts_folder <- dirname(STATE_PRECINCT_SOURCE_FILE)
copy_shapefile_folder(state_precincts_folder, NAME_CORRECTION_OUTPUT_FOLDER)
st_write(
  state_precincts,
  file.path(NAME_CORRECTION_OUTPUT_FOLDER, basename(STATE_PRECINCT_SOURCE_FILE)),
  append = FALSE
)

copy_shapefile_folder(NAME_CORRECTION_OUTPUT_FOLDER, state_precincts_folder)
