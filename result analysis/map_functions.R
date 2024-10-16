library(data.table)
library(ggplot2)
library(lubridate)
library(sf)
library(cartogram)

######
#General process
######

# The mapping files are set to run independently of the graph files.
# These functions associate demographics and average distances to each 
# county and optimization run separately
# NOTE: Right now, the these maps are not completely adapted to denote when
#		the incoming data includes driving distances. This is a future feature

# Work flow:
###########
# 1. make_or_load_maps:
#	 * creates a base map or cartogram with associated census demographic data. 
#		* Only Census data used for this. 
#		* No optimization data involved
#    	* WARNING: If making cartograms, make certain that the final error is acceptable. This is not currently automated
#	 * process_demographics puts together a single datatable of relevant P3 and P4 census data
#	 * process_maps pulls out the block group level shape files
#	 * These two get merged and written to file
# 2. make_bg_maps:
#	 * takes base maps of cartograms and associates average distance traveled to each block group
# 	 * aggregate_residence:
#	 	* takes the output of the optimization process and aggregates average distance up to the block group level
#	 	* the aggregation is done by removing the last three digits of the block group id
#	 	* returns only the distance data for a specific demographic group
#    * merge optimization data with map data
#	 * produce a map or cartogram colored by distance to asigged location
#	 	* if a map, put the polling locations on the map as well
#	 	* distance_bounds: the color bounds are set for ALL the maps in the config_folder
# 3. make_demo_dist_map:
#	 * only a map, not a cartogram
# 	 * same as above, but places a dot in each block representing a demographic group
#	 * the color is as above
#	 * the size of the dot corresponds to population. 
# 	 	* the size scale is determined by the total populations of the block groups

source('result analysis/graph_functions.R')

split_data <- function(data, config_dt){
	#take entire residence data from a config_set, split by config_set
	#merge with config_data to get location
	
	#get config meta data and locations
	config_set_location <- config_dt[ , .(location, config_set, config_name)]
	#merge
	data_with_loc <- merge(data, config_set_location, by = c('config_set', 'config_name'))
	data_with_loc_list <- split(data_with_loc, data_with_loc$config_name)

	return(data_with_loc_list)
}

distance_bounds <- function(residence_df){
	#calculate the min and max average distances traveled by census block for maps by location

	#select total population residence data
	pop_res_dist <- residence_df[demographic == 'population', ]
	
	# pull out min and max average distances by location
	bound_dt <- pop_res_dist[, .(min_avg_dist = min(avg_dist), max_avg_dist = max(avg_dist)), by = location]
	return(bound_dt)
}


process_maps <- function(file_name){
    #read in map data as data table
    map <-st_read(file_name)
    map_dt <- as.data.table(map)
    #add column for total area, keep only id, area, shape
    map_dt <- map_dt[ , AREA20 := ALAND20 + AWATER20
				][ , .(GEOID20, AREA20, INTPTLAT20, INTPTLON20, geometry)]
    return (map_dt)
}


process_demographics <-function(folder_name){
#Take P3 and P4 tables from the indicated folder and makes a combined demographics table

    #read in demographics
    P4 = paste(folder_name, 'DECENNIALPL2020.P4-Data.csv', sep = '/')
    P3 = paste(folder_name, 'DECENNIALPL2020.P3-Data.csv', sep = '/')
    P3_demo <- fread(P3, skip = 1, header = T)
    P4_demo <- fread(P4, skip = 1, header = T)
    #clean up data
    #select "Geography" "Geographic Area Name" and demographic columns
    P3_demo<-P3_demo[,c(1:3,5:11 )]
    P4_demo<-P4_demo[,c(1:2, 4:5)]
    #Change Population column name
    setnames(P3_demo, names(P3_demo)[3:10], c('population',
    'white','black', 'native', 'asian', 'pacific_islander',
    'other', 'multiple_races'))
    setnames(P4_demo, names(P4_demo)[3:4], c("hispanic", 'non_hispanic'))
    #merge to get all demographics
    demo = merge(P3_demo, P4_demo, by = c('Geography', 'Geographic Area Name'), all = TRUE)
    #Change geography tag to match mapping data
    demo = demo[, Geography := sub(".*US", '', Geography)]
	#drop empty block groups
	demo = demo[population >0, ]
}

aggregate_residence <- function(res_dist_df, demo_str){
	#aggregate residence data from the model output, which is at the block 
	#level, to the block group level,
	#selecting for the given demographic

	#the last 3 digits of id_orig are the block, remove these for block group
	#GEOID20 is the BG column name from the census
	res_dist_df <- res_dist_df[ , id_orig := as.character(id_orig)
		][ , GEOID20 := gsub('.{3}$', '', id_orig)]
	
	#aggregate by block group, demographic and config_name
	bg_res_dist <- res_dist_df[ , .(demo_pop = sum(demo_pop),weighted_dist = sum(weighted_dist)), 
						by = c('GEOID20', 'demographic', 'config_name')][ , avg_dist := weighted_dist/demo_pop]

	#select demographic
	bg_res_demo_dist <- bg_res_dist[demographic == demo_str, ]
	return(bg_res_demo_dist)
}


make_or_load_maps <- function(location, map_type, demographic = 'population'){
	#checks if the desired map .csv already exists, and load it if it does
	#else, makes the map by loading the census shape and demographic data
	#and merging.
	#1. set a name for a map
	#2. check if the map exists. if so, load, else
	#2a. get block group level demographics
	#2b. get block group shape files
	#2c. merge shape file with demographics, assign projection
	#2d. make map and write to file

	#1. name the desired map
	if (map_type == 'cartogram'){
		map_name<- paste0(location, "_", map_type, '_', demographic, '.shp')
	} else if (map_type == 'map'){
		map_name<- paste0(location, "_", map_type, '.shp')
	} else if (map_type == 'boundries'){
		map_name<- paste0(location, "_", map_type, '.shp')
	} else{
		stop('map_type must be either map, boundries or cartogram')
	}
	map_folder <- 'result analysis/map work'
	
	#2. load if it exists, else make
	print(map_name)
	if (file.exists(file.path(here(), map_folder, map_name))){
		map <- st_read(file.path(here(), map_folder, map_name))
		#name resetting needed because of st_write truncating names
		names(map) <- c("GEOID20", "AREA20", "INTPTLAT20", "INTPTLON20", "Geographic Area Name", "population", "white", "black", "native", "asian", "pacific_islander", "other", "multiple_races", "hispanic", "non_hispanic", "geometry")
	} else { 
		#2a. get block group demographics
		if (map_type == 'boundries') { #associate block group demographics based on included blocks only

		#get block level demographics
		block_demo <- process_demographics(paste0(here(), '/datasets/census/redistricting/', location))
		#define columns for aggregation
		demo_names <- names(block_demo)[sapply(block_demo,is.integer) ==TRUE]		
		#aggregate up to block group level
		bg_demo <- block_demo[ , Geography := gsub('.{3}$', '', Geography)
							][ ,`Geographic Area Name` := gsub('^.{12}', '',`Geographic Area Name` )
							][ , lapply(.SD, sum), by = c('Geography','Geographic Area Name'), .SDcols = demo_names]
		} else { # get demographics from block groups
		bg_demo <- process_demographics(paste0(here(), '/datasets/census/redistricting/', location, "/block group demographics"))
		}
		#2b. get shape file
		#Block group shape files
		if (map_type == 'boundries') {
			bg_shape_file <- list.files(paste0(here(), '/datasets/census/tiger/',gsub('Contained_in', 'Intersecting', location) ), pattern = 'bg20.shp$')
			#get map data
			map_bg_dt <- process_maps(paste0(here(), '/datasets/census/tiger/', gsub('Contained_in', 'Intersecting', location) , '/', bg_shape_file))
		} else {
			bg_shape_file <- list.files(paste0(here(), '/datasets/census/tiger/', location ), pattern = 'bg20.shp$')
			#get map data
			map_bg_dt <- process_maps(paste0(here(), '/datasets/census/tiger/', location, '/', bg_shape_file))
		}
		#2c. merge the bg shape dt with the bg demo dt
		bg_demo_shape <- merge(map_bg_dt, bg_demo, by.x = c('GEOID20'), by.y = c('Geography'))
		#make it an sf object for mapping
		bg_demo_sf <- st_as_sf(bg_demo_shape)
		#assign it a projection
		if (map_type %in% c('map','boundries')){ 
			projection = 4326 #must use this projection if you want to add points to map
		} else {
			projection = 3857 #correct projection for merc
		}
		#2d. make map and write to file
		map <- st_transform(bg_demo_sf, projection)
		if (map_type == 'cartogram'){
			map <- cartogram_cont(map, demographic, itermax = 200, maxSizeError = 1.02)
			
		}
		st_write(map, file.path(here(), map_folder, map_name))
	}
	return(map)
}

make_bg_maps <-function(res_data, result_data, config_data, map_type, result_folder_name = result_folder,  demo_str = 'population', driving_flag = DRIVING_FLAG){
	#use residence_distances to color the map by distance to matched location, for the indicated demographic
	#If the map type is "map", then also plot the polling locations

	#aggregate block level demographic data to block group level
	res_dist_demo <- aggregate_residence(res_data, demo_str)

	#get lat/ lon coords from results
	dest_lat_lon <- result_data[ ,.(long = unique(dest_lon), lat = unique(dest_lat), type = unique(dest_type)), by = c('id_dest', 'config_name')]

	#combine with residence data
	res_dist_demo_dest <- merge(dest_lat_lon, res_dist_demo)

	#split residence and result data
	#result_list <- split_data(result_data, config_data)
	#res_dist_demo_list <- split_data(res_dist_demo, config_data)

	#get the location from the data
	location <- unique(res_dist_demo$location)
	
	#extract demographics from map
	#must do this way because map is an sf object, not a data.table
	if (map_type == 'cartogram'){
		warning('Using cartograms is deprecated due to difficulties with convergence of the map.')
		map_demo_list = lapply(location, function(x){make_or_load_maps(x, map_type, demo_str)})
		map_name = paste('distance', demo_str, map_type, sep = '_')
	}else if (map_type %in% c('map', 'boundries')) { #map_type !=cartogram
		#note, in this case we make a population level map
		map_demo_list = lapply(location, make_or_load_maps(x, map_type))
		map_name = paste('distance', map_type, sep = '_')
	} else {
		stop('map_type must be either map, cartogram or boundries')
	}

	#combine with res_dist_demo with map
	geom_cols <- c('GEOID20', 'geometry')
	map_sf_list <- lapply(map_demo_list, function(x){x[, geom_cols]})
	demo_dist_shape<- lapply(map_sf_list, function(x){merge(x, res_dist_demo, all = T)})	
	
	#make maps
	if (driving_flag){
		title_str = 'Average driving distance to poll (m)'
		fill_str = 'Avg driving distance (m)'
	} else{
		title_str = 'Average distance to poll (m)'
		fill_str = 'Avg straight line distance (m)'
	}

	## START HERE. 
	county = gsub('.{3}$','', location)
	numeric_label = str_extract(file_to_map, '[0-9]+')
	descriptor = paste(county, numeric_label, sep ='_')
	plotted <- ggplot() +
		geom_sf(data = demo_dist_shape, aes(fill = avg_dist)) + 
		scale_fill_gradient(low='white', high='darkgreen', limits = c(color_bounds[[1]], color_bounds[[2]]), name = fill_str) 
	if (map_type != 'cartogram'){
		plotted = plotted + 
		geom_point(data = ev_locs, aes(x = long, y = lat, color = type))+ 
		scale_color_manual(breaks = c('polling', 'potential', 'bg_centroid'), values = c('red', 'black', 'dimgrey'), name = 'Poll Type') +  xlab('') + ylab('') 
	} else{ 
		plotted = plotted + theme(axis.text.x=element_blank(), axis.text.y=element_blank(), axis.ticks = element_blank())
	}
	plotted = plotted + ggtitle(title_str, paste('Block group', map_type , 'of', gsub('_', ' ', descriptor) ))

	if (driving_flag){
	plotted <- plotted #+ labs(fill = 'Avg driving distance (m)')
	} else {
		plotted <- plotted #+ labs(fill = 'Avg straight line distance (m)')
	}

	#write to file
	descriptor = gsub(".*configs.(.*)_res.*", "\\1", file_to_map)
	num_polls <- str_extract(descriptor, '[0,-9]+')
	ggsave(paste0(here(), '/', plot_folder, '/',map_name, '_',descriptor, '_','polls.png'), plotted)
	}

make_demo_dist_map <-function(res_data, demo_str, result_folder_name = result_folder, this_location = LOCATION, map_type = 'map', driving_flag = DRIVING_FLAG){

	#read in block level data and aggregate to block group level
	res_dist_df <- aggregate_residence(res_data, demo_str)
	#get map
	map_demo_list <- make_or_load_maps(this_location, map_type)
	geom_cols <- c('GEOID20', 'INTPTLON20', 'INTPTLAT20', 'geometry')
	map_sf <- map_demo_list[, geom_cols]
	#change lat/lon to numeric
	map_sf$INTPTLON20 <- as.numeric(map_sf$INTPTLON20)
	map_sf$INTPTLAT20 <- as.numeric(map_sf$INTPTLAT20)

	#merge
	demo_dist_shape<- merge(map_sf, res_dist_df, all = T)

	#plot map with a point at the centroid, colored by distance, sized by size
	#set names
	if (driving_flag){
		title_str = 'population average driving distance to poll (m)'
		color_str = 'Avg driving distance (m)'
	} else{
		title_str = 'population average distance to poll (m)'
		color_str = 'Avg straight line distance (m)'
	}

	county = gsub('.{3}$','',this_location)
	numeric_label = str_extract(file_to_map, '[0-9]+')
	descriptor = paste(county, numeric_label, sep ='_')
	#size limits
	pop_dist_df <- aggregate_residence(res_data, 'population')
	max_pop <- max(pop_dist_df$demo_pop)
	print(max_pop)
	plotted <- ggplot() +
		geom_sf(data = demo_dist_shape) +  
		geom_point(data = demo_dist_shape, aes(x = INTPTLON20, y = INTPTLAT20, size= demo_pop, color = avg_dist)) +
		scale_color_gradient(low='white', high='darkgreen', limits = c(color_bounds[[1]], color_bounds[[2]]), name = color_str) + 
		labs(size = paste(demographic_legend_dict[demo_str], 'population') ) + 
		xlab('') + ylab('') + scale_size(limits= c(0, max_pop)) + 
		ggtitle(paste(demographic_legend_dict[demo_str], title_str), paste('Block groups in', gsub('_', ' ', descriptor)))

	#write to file
	descriptor = gsub(".*configs.(.*)_res.*", "\\1", file_to_map)
	num_polls <- str_extract(descriptor, '[0,-9]+')
	ggsave(paste0(here(), '/', plot_folder, '/', demo_str, '_','pop_and_dist','_',descriptor, '_','polls.png'), plotted)

}


#########
#other stuff
#########


#bg_area_pop <- merge(demo_dt, maps_bg_dt, by.x = 'Geography', by.y = 'GEOID20')

#pop_sf <- st_as_sf(bg_area_pop)
#########
#make maps
#########

#pop_merc <- st_transform(pop_sf, 3857)

#ggplot() +  geom_sf(data = pop_merc)

#Gwinnett_cartogram <- cartogram_cont(pop_merc, "Population")

#ggplot() +  geom_sf(data = Gwinnett_cartogram)



