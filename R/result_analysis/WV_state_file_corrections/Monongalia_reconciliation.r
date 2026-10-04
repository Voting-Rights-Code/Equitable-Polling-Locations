library(data.table)
library(here)

setwd(here())
source("R/result_analysis/utility_functions/precinct_shape_functions.r")
source("R/result_analysis/precinct_configs/Monongalia_County_WV.r")

########
# Reconciliation script for Monongalia County, WV -- builds the
# polling-location crosswalk from a human-reviewed
# location_precinct_mismatches.csv. Re-run whenever new rows are added to
# that file (see check_poll_precinct_agreement()'s instructions for when
# that happens).
########

########
# Standard work flow: 
# 1. Run flag_state_provided_precincts.r
# 2. run extract_precincts.r
# 3. halt if state and county files don't match
# 4. user updates mismatch file
# 5. run reconciliation file
# 6. run extract_precincts.r
# 7. If mismatch file is changed, rerun reconciliation and extract precincts files
########

########
# CHANGELOG -- append a new dated entry each time new rows are reviewed.
# This is human-readable narrative alongside the real record: git history on
# location_precinct_mismatches.csv itself (kept un-ignored in .gitignore for
# exactly this reason) is what actually preserves every past round's
# reviewed content, since each new run overwrites that file in place.
#
# 2026-07-09, state file vintage "VotingPrecincts_20260424_wmA84":
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
# just a field updated) -- apply_corrections()/build_precinct_crosswalk()
# handle that generically from the resolution_type column, nothing hardcoded
# here.
########

########
# Input:  location_precinct_mismatches.csv (human-reviewed)
# Output: precinct_polling_location_crosswalk.csv, read by extract_precincts.r
#         to resolve each block's final polling destination.
########

#change directory
precinct_analysis_output_folder <- file.path("precinct_analysis_outputs", LOCATION)
setwd(precinct_analysis_output_folder)

#read in correction data
RECONCILIATION_CSV <- "location_precinct_mismatches.csv"
reconciliation_data <- safe_fread(RECONCILIATION_CSV)

#build crosswalk
crosswalk <- build_precinct_crosswalk(reconciliation_data)

#write to file. 
crosswalk_path <- "precinct_polling_location_crosswalk.csv"
fwrite(crosswalk, crosswalk_path)
