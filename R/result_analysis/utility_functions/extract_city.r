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

P3 = 'DECENNIALPL2020.P3-Data.csv'
P4 = 'DECENNIALPL2020.P4-Data.csv'


#runtime
BLOCK_GEOMETRY_FILES = 'tl_2020_13051_tabblock20'
BG_GEOMETRY_FILES = 'tl_2020_13051_bg20'
LOCATION_BASE= 'Savannah_City_of_GA'
LOCATION_SUP = paste('Intersecting', LOCATION_BASE, sep = '_')
LOCATION_SUB = paste('Contained_in', LOCATION_BASE, sep = '_')
CITY_LIMIT_FOLDER = LOCATION_BASE
CONTAINING_COUNTY = 'Chatham_County_GA'
CITY_LIMIT_FILE = 'City_Limit'


######Functions#######

get_shape_data <- function(shape_file_name){
    #get name of file
    shape_file<- paste0(TIGER_FOLDER, '/', CONTAINING_COUNTY, '/', shape_file_name, '.shp')
    #read data
    shape_data <- st_read(shape_file)
    #transform data
    shape_data <- st_transform(shape_data, CRS_PROJECTION)
    return(shape_data)
}

#select intersecting or contained shape data from a county, given a city file
get_shapes_for_city <- function(city_shape_data, county_shape_data, intersection_flag){
    # make data planar. Otherwise the following line throws an error
    sf_use_s2(FALSE)

    #choose intersecting or contained data
    if (intersection_flag){
        indices <- st_intersects(city_shape_data, county_shape_data, sparse = T)
    }   
    else{
    indices <- st_contains(city_shape_data, county_shape_data, sparse = T)
    }
    all_indices <- Reduce(union, indices)
    relevant_shapes <- county_shape_data[all_indices, ]
    return(relevant_shapes)
}

#crop the shapes to be in the city limits, and assign new interior points
crop_to_city_lines <- function(city_shape_data, county_shape_data){
    #crop shapes
    cropped_shapes <- st_intersection(city_shape_data, county_shape_data)

    #in case of multiple connected components make each component unique
    cropped_shapes$GEOID20 <- gsub('X','',make.names(cropped_shapes$GEOID20, unique = TRUE))

    #create interior point for cropped shapes
    interior_pt <- st_point_on_surface(cropped_shapes)
    #calculate a new INTPTLAT20/INTPTLON20 column 
    interior_pt$INTPTLAT20= st_coordinates(interior_pt)[, 2]
    interior_pt$INTPTLON20 = st_coordinates(interior_pt)[, 1]
    
    #Keep the shape data for joining
    df_shape <- cropped_shapes[c('GEOID20',"geometry" )]
    #drop the geometry from the point data for joining
    interior_pt$geometry <- NULL

    #Join the data and remove columns created by intersection
    df <- merge(df_shape, interior_pt, by = 'GEOID20', how = left)
    extra_columns <- c("OBJECTID", "SHAPESTAre", "SHAPESTLen")
    df <- df[ , !(names(df) %in% extra_columns)]
    return(df)
}

write_to_file <- function(shape_data, location_folder, file_name){
    #check if requisite folder exists, or create it
    shape_folder = paste0(TIGER_FOLDER, '/', location_folder)
    if (!file.exists(file.path(here(), shape_folder))){
        dir.create(file.path(here(), shape_folder))
    }

    #write to file
    st_write(shape_data, paste0(shape_folder, '/',  file_name, '.shp'), append = FALSE)
}

subset_and_write_demo_data <- function(city_shape_data, demo_type, location, bg_flag){
    #read county demo data, skipping first header
    if (bg_flag){
        county_demo_folder = paste0(REDISTRICTING_FOLDER, '/', CONTAINING_COUNTY, '/', DEMO_BG_FOLDER)
        city_demo_folder = paste0(REDISTRICTING_FOLDER, '/', location, '/', DEMO_BG_FOLDER)
    } else{
        county_demo_folder = paste0(REDISTRICTING_FOLDER, '/', CONTAINING_COUNTY)
        city_demo_folder = paste0(REDISTRICTING_FOLDER, '/', location)
    }
    #get header rows. We will append these later
    headers <- fread(paste0(county_demo_folder, '/', demo_type), nrow = 2)

    #read in county data
    county_demo <- fread(paste0(county_demo_folder, '/', demo_type), skip = 1, header = T)
    
    #extract prefix from Geography column for merging
    prefix = sub('(US).*', '\\1',county_demo$Geography[1])

    #get unique elements of city_shape data
    city_ids <- data.table(GEOID20 = city_shape_data$GEOID20)

    #reformat ids for merging
    city_ids[ , GEOID20:= paste0(prefix, city_ids$GEOID20)  #add prefix in
            ][ , GEOID20DUP := gsub('\\..*', '', GEOID20)] #remove suffix for merge
    
    #merge
    city_demo <- merge(city_ids, county_demo, by.x = 'GEOID20DUP', by.y = 'Geography', how = 'left' )
    city_demo$GEOID20DUP <- NULL
    #write to file, check if it exists first
    if (!file.exists(file.path(here(), city_demo_folder))){
        dir.create(file.path(here(), city_demo_folder))
    }

    #replace the names and add header rows before writing
    names(city_demo) <- names(headers)
    city_demo <- rbind(headers, city_demo)
    fwrite(city_demo, paste0(city_demo_folder, '/', demo_type), append = FALSE, col.names = FALSE)
}


######Get shape data#######
county_blocks <- get_shape_data(BLOCK_GEOMETRY_FILES)
county_bgs <- get_shape_data(BG_GEOMETRY_FILES)
city_shape <- get_shape_data(paste0(CITY_LIMIT_FOLDER, '/', CITY_LIMIT_FILE))

######compute intersecting and contained blocks and block groups######
intersecting_blocks <- get_shapes_for_city(city_shape, county_blocks, TRUE)
contained_blocks <- get_shapes_for_city(city_shape, county_blocks, FALSE)

intersecting_bgs <- get_shapes_for_city(city_shape, county_bgs, TRUE)
contained_bgs <- get_shapes_for_city(city_shape, county_bgs, FALSE)

#####plot, just to see that city blocks is, indeed what one wants #####
ggplot() +
		geom_sf(data = intersecting_blocks, fill = 'red', alpha = .5) + 
		geom_sf(data = city_shape, fill = 'yellow', alpha = .5) +
        geom_sf(data = contained_blocks, fill = 'blue', alpha = .5)  
ggsave(paste0(TIGER_FOLDER, '/', CONTAINING_COUNTY, '/', CITY_LIMIT_FOLDER, '/', 'block_selection_options.png'))

ggplot() +
		geom_sf(data = intersecting_bgs, fill = 'red', alpha = .5) + 
		geom_sf(data = city_shape, fill = 'yellow', alpha = .5) +
        geom_sf(data = contained_bgs, fill = 'blue', alpha = .5)  
ggsave(paste0(TIGER_FOLDER, '/', CONTAINING_COUNTY, '/', CITY_LIMIT_FOLDER, '/', 'bg_selection_options.png'))

#get dataframe of city_blocks intersecting the city limits and write to file
#st_write(city_blocks, paste0(TIGER_FOLDER, '/', LOCATION, '/',  BLOCK_GEOMETRY_FILES, '.shp'))


#######
#crop intersecting blocks and assign new interior points 
#######
cropped_blocks <- crop_to_city_lines(city_shape, intersecting_blocks)
cropped_bgs <- crop_to_city_lines(city_shape, intersecting_bgs)
    #THIS IS A MANUAL CLUDGE TO AVOID A SPECIFIC ERROR.
    cropped_bgs$geometry_type <- st_geometry_type(cropped_bgs$geometry, by_geometry = T)
    cropped_bgs <- cropped_bgs[cropped_bgs$geometry_type != 'GEOMETRYCOLLECTION', ]
    cropped_bgs$geometry_type <- NULL

contained_blocks <- crop_to_city_lines(city_shape, contained_blocks)
contained_bgs <- crop_to_city_lines(city_shape, contained_bgs)

########write shape data to file #########
write_to_file(cropped_blocks, LOCATION_SUP, BLOCK_GEOMETRY_FILES)
write_to_file(contained_blocks, LOCATION_SUB, BLOCK_GEOMETRY_FILES)

write_to_file(cropped_bgs, LOCATION_SUP, BG_GEOMETRY_FILES)
write_to_file(contained_bgs, LOCATION_SUB, BG_GEOMETRY_FILES)

########write demo data to file #########
#blocks
subset_and_write_demo_data(cropped_blocks, P3, LOCATION_SUP, FALSE)
subset_and_write_demo_data(cropped_blocks, P4, LOCATION_SUP, FALSE)

subset_and_write_demo_data(contained_blocks, P3, LOCATION_SUB, FALSE)
subset_and_write_demo_data(contained_blocks, P4, LOCATION_SUB, FALSE)

#block groups
subset_and_write_demo_data(cropped_bgs, P3, LOCATION_SUP, TRUE)
subset_and_write_demo_data(cropped_bgs, P4, LOCATION_SUP, TRUE)

subset_and_write_demo_data(contained_bgs, P3, LOCATION_SUB, TRUE)
subset_and_write_demo_data(contained_bgs, P4, LOCATION_SUB, TRUE)

