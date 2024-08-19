library(data.table)
library(sf)
library(here)
library(ggplot2)


setwd(here())

########Set constants######## 
#global
TIGER_FOLDER = 'datasets/census/tiger'
REDISTRICTING_FOLDER = 'datasets/census/redistricting'
DEMO_BG_FOLDER = 'block group demographics'
CRS_PROJECTION = 4326

BLOCK_GEOMETRY_FILES = 'tl_2020_55025_tabblock20'
BG_GEOMETRY_FILES = 'tl_2020_55025_bg20'
P3 = 'DECENNIALPL2020.P3-Data.csv'
P4 = 'DECENNIALPL2020.P4-Data.csv'


#runtime
LOCATION_BASE= 'Savannah_City_of_GA'
LOCATION_SUP = paste('Intersecting', LOCATION_BASE, sep = '_')
LOCATION_SUB = paste('Contained_in', LOCATION_BASE, sep = '_')
CITY_LIMIT_FOLDER = LOCATION_BASE
CONTAINING_COUNTY = 'Chatham_County_GA'
CITY_LIMIT_FILE = 'City_Limit'


######process map data#######
#alderman data from https://data-sagis.opendata.arcgis.com/datasets/c8a3b716a9de42fd9a6936c7058016de_7/explore?location=31.968933%2C-81.071600%2C9.83
#May 29, 2024 version
read_location_alderman <- paste0(TIGER_FOLDER, '/', CONTAINING_COUNTY, '/', LOCATION_BASE, '/','Aldermanic_Districts_(Savannah)_.shp')
#Precint data from personal communication from Juanma Balcazar
read_location_precincts <- paste0(TIGER_FOLDER, '/', CONTAINING_COUNTY, '/', LOCATION_BASE, '/','GA-PRECINCTS2022-SHAPE.shp')
write_location_final <- paste0(TIGER_FOLDER, '/', CONTAINING_COUNTY, '/', LOCATION_BASE, '/',CITY_LIMIT_FILE, '.shp')
alderman <- st_read(read_location_alderman)
ggplot() + geom_sf(data = alderman, fill = 'red', alpha = .5)

savannah_union <- st_union(alderman)
ggplot() + geom_sf(data = savannah_union, fill = 'red', alpha = .5)
ggsave(paste0(TIGER_FOLDER, '/', CONTAINING_COUNTY, '/', CITY_LIMIT_FOLDER, '/', 'alderman_city_limit_map.png'))
savannah_union <- st_transform(savannah_union, CRS_PROJECTION)
st_write(savannah_union, write_location_final, append = FALSE)

savannah_combine <- st_combine(alderman)
ggplot() + geom_sf(data = savannah_combine, fill = 'blue', alpha = .5)

precincts <- st_read(read_location_precincts)
savannah_precincts

