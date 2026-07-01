library(data.table)
library(here)

setwd(here())

########
# One-off: convert temp/Precincts_by_Location.csv (one row per polling
# location, with repeated "Prec" columns listing the precincts it serves)
# into a long-format file (one row per precinct) at
# temp/Precincts_by_Location_long.csv, to test whether the #268/#282
# reconciliation pipeline handles a long-format county source file.
########

source("R/result_analysis/Extraction_configs/Monongalia_County_WV.r")

provided_polls <- fread(COUNTY_PROVIDED_PRECINCT_FILE)

precinct_column_numbers <- which(names(provided_polls) %in% COUNTY_PRECINCT_COLUMN_NAMES)
unique_precinct_columns <- make.unique(names(provided_polls)[precinct_column_numbers])
setnames(provided_polls, old = precinct_column_numbers, new = unique_precinct_columns)

precincts_long <- melt(
  provided_polls,
  id.vars = c(COUNTY_POLLING_LOCATION_NAME_COL, COUNTY_POLLING_LOCATION_ADDRESS_COL),
  measure.vars = unique_precinct_columns,
  value.name = "Precinct",
  na.rm = TRUE
)
precincts_long <- precincts_long[Precinct != ""]
precincts_long[, variable := NULL]

fwrite(precincts_long, "temp/Precincts_by_Location_long.csv")
