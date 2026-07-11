library(sf)
library(here)

setwd(here())

########
# Pull just the precinct layer (FeatureServer/0 -- "Precincts") from
# Monongalia County's public ArcGIS Online voting district map
# (https://www.arcgis.com/apps/webappviewer/index.html?id=f387eb0c2d5b4cce90e00f11354d4f9b),
# which also hosts unrelated layers (magisterial districts, executive
# committee districts, senate/house districts, addressing) on the same
# service host -- only layer index 0 is the precinct boundary data.
########

precinct_layer_query_url <- paste0(
  "https://services3.arcgis.com/MGBEQZtkTlJin8UB/arcgis/rest/services/",
  "Monongalia_County_Precincts/FeatureServer/0/query",
  "?where=1=1&outFields=*&returnGeometry=true&f=geojson"
)

county_precincts <- st_read(precinct_layer_query_url)

# ArcGIS-computed Shape__Area/Shape__Length columns collide once truncated to
# the ESRI Shapefile driver's 10-character field name limit; drop them since
# they're redundant with the geometry itself.
county_precincts <- county_precincts[
  , !(names(county_precincts) %in% c("Shape__Area", "Shape__Length"))
]

output_folder <- "datasets/precincts/Monongalia_County_WV"
if (!file.exists(file.path(here(), output_folder))) {
  dir.create(file.path(here(), output_folder), recursive = TRUE)
}

st_write(
  county_precincts,
  file.path(output_folder, "Monongalia_County_Precincts.shp"),
  append = FALSE
)
