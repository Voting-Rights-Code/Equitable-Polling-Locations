library(data.table)
library(sf)
library(here)
library(ggplot2)

setwd(here())

########Set constants######## 
#global
TIGER_FOLDER = 'datasets/census/tiger'
CITY_LIMIT_FOLDER = 'city_boundaries'
CRS_PROJECTION = 4326

#runtime
LOCATION = 'Madison_City_of_WI'
CONTAINING_COUNTY = 'Dane_County_WI'
CITY_LIMIT_FILE = 'City_Limit'
BLOCK_GEOMETRY_FILES = 'tl_2020_55025_tabblock20'

######Get shape data#######
county_block_file <- paste0(TIGER_FOLDER, '/', CONTAINING_COUNTY, '/', BLOCK_GEOMETRY_FILES, '.shp')
county_blocks <- st_read(county_block_file)
county_blocks <- st_transform(county_blocks, CRS_PROJECTION)

city_shape_file <- paste0(TIGER_FOLDER, '/', LOCATION, '/', CITY_LIMIT_FOLDER, '/', CITY_LIMIT_FILE, '.shp')
city_shape <- st_read(city_shape_file)
city_shape <- st_transform(city_shape, CRS_PROJECTION)


####plot overlayed data#####
plot(st_geometry(city_shape))
plot(county_blocks, add = T)

######compute intersection and overlap######
sf_use_s2(FALSE) # make data planar. Otherwise the following line throws an error

#get indices constained in each connected component of city shape
block_indices <- st_intersects(city_shape, county_blocks, sparse = T)
#get unique list of block indices from all connected compoents
all_block_indices <- Reduce(union, block_indices)

contained_indices<-st_contains(city_shape, county_blocks, sparse = T)
all_contained_indices <- Reduce(union, contained_indices)
contained_blocks <- county_blocks[all_contained_indices, ]
#get dataframe of city_blocks intersecting the city limits and write to file
city_blocks <- county_blocks[all_block_indices, ]
st_write(city_blocks, paste0(TIGER_FOLDER, '/', LOCATION, '/',  BLOCK_GEOMETRY_FILES, '.shp'))

#####plot, just to see that city blocks is, indeed what one wants #####
ggplot() +
		geom_sf(data = city_blocks, fill = 'red', alpha = .5) + 
		geom_sf(data = city_shape, fill = 'yellow', alpha = .5) +
        geom_sf(data = contained_blocks, fill = 'blue', alpha = .5)  
ggsave(paste0(TIGER_FOLDER, '/', LOCATION, '/', CITY_LIMIT_FOLDER, '/', 'block_selection_options.png'))

#crop the blocks file to be in the 
foo <- st_intersection(city_blocks, city_shape)

ggplot() +
		#geom_sf(data = city_blocks, fill = 'red', alpha = .5) + 
		geom_sf(data = city_shape, fill = 'yellow', alpha = .5) +
        geom_sf(data = foo, fill = 'blue', alpha = .5) 

foo$