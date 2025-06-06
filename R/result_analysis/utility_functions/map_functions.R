library(data.table)
library(ggplot2)
library(sf)

source('R/result_analysis/utility_functions/load_config_data.R')
source('R/result_analysis/utility_functions/storage.R')

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
#	 * NOTE: no longer support cartograms.
#	 * furthermore, no longer writes map data to file as an intermediate step

# 1. make_or_load_maps:
#	 * creates a base map associated census demographic data.
#		* Only Census data used for this.
#		* No optimization data involved
#		* if map_type = boundary, then all boundaries that  
#	 * process_demographics puts together a single datatable of relevant P3 and P4 census data
#	 * process_maps pulls out the block group level shape files
#	 * These two get merged and written to file
# 2. make_bg_maps:
#	 * takes base maps and associates average distance traveled to each block group
# 	 * aggregate_residence:
#	 	* takes the output of the optimization process and aggregates average distance up to the block group level
#	 	* the aggregation is done by removing the last three digits of the block group id
#	 	* returns only the distance data for a specific demographic group
#    * merge optimization data with map data
#	 * produce a map colored by distance to asigged location
#	 	* if a map, put the polling locations on the map as well
#	 	* distance_bounds: the color bounds are set for ALL the maps in the config_folder
# 3. make_demo_dist_map:
#	 * only a map or boundary
# 	 * same as above, but places a dot in each block representing a demographic group
#	 * the color is as above
#	 * the size of the dot corresponds to population.
# 	 	* the size scale is determined by the total populations of the block groups


###########
#Adjoin shape and demographic data 
#needed for maps and regressions both
###########


process_maps <- function(shp_file_name){
	#reads in map data, ads an area column and returns only
	#polygon id (GEOID20), the area, centroid, and polygon geometry

    #read in map data as data table
    map <-st_read(shp_file_name)
    map_dt <- as.data.table(map)
    #add column for total area, keep only id, area, shape
    map_dt <- map_dt[ , AREA20 := ALAND20 + AWATER20
				][ , .(GEOID20, AREA20, INTPTLAT20, INTPTLON20,
				geometry)]
    return (map_dt)
}

get_map_file <- function(location, block_flag){
	map_folder <- paste0(here(),'/datasets/census/tiger/', location, '/')
	if(block_flag){
		shp_pattern = 'tabblock20.shp$'
	}else{
		shp_pattern = 'bg20.shp$'
	}
	map_file <- paste0(map_folder, list.files(map_folder, pattern = shp_pattern))		

	return(map_file)
}

results_with_area_geom<- function(location, result_df){
	#takes a result df, and a location
	#pulls the block level tiger data
	#merges the area and geometry data into result data
	
	#get block level map name
	map_file <- get_map_file(location, block_flag = TRUE)
	#extract columns
	map_data<- process_maps(map_file)
	#merge with results
	results_with_geom <- merge(result_df, map_data, by.y = c('GEOID20'), by.x = c('id_orig'), all.y = TRUE)
	#drop centroid because have orig_lat, orig_lon
	results_with_geom <- results_with_geom[, `:=`(INTPTLAT20 = NULL, INTPTLON20 = NULL)]
	return(results_with_geom)
}

demographically_weighted_distances <- function(result_df){
	#takes a result df and calculates the weighted distance for each demographic group
	#in block
	weighted_df <- result_df[,lapply(.SD, function(x)distance_m*x), by = c('id_orig', 'config_name', 'config_set', 'descriptor'), .SDcols = DEMO_COLS]

	return(weighted_df)
}

bg_result_geom <- function(location, result_df){
	#input results and geometry and block level
	#aggregate to block group level
	#compute block level average distance
	#Merge in block group centroid coordinate and geometry
	
	#block level results and geom
	block_result_geom <- results_with_area_geom(location, result_df)

	#block level weighted distances
	block_weighted_dist <- demographically_weighted_distances(result_df)

	#drop last three digits of id_orig to get block group
	bg_result_geom <- block_result_geom[ , bg_id := gsub('.{3}$', '', id_orig)]
	bg_weighted_dist <- block_weighted_dist[ , bg_id := gsub('.{3}$', '', id_orig)]

	#aggregate demographics to block group level
	bg_demo <- bg_result_geom[ , lapply(.SD, sum), by = c('bg_id','config_set', 'config_name', 'descriptor'), .SDcols = DEMO_COLS]
	bg_weight <- bg_weighted_dist[ , lapply(.SD, sum), by = c('bg_id','config_set', 'config_name', 'descriptor'), .SDcols = DEMO_COLS]

	#melt both
	id_cols = c('bg_id','config_set', 'config_name', 'descriptor')
	demo_data_long <- melt(bg_demo, id.vars = id_cols, measure.vars = DEMO_COLS, value.name ='demo_pop' , variable.name = "demographic")
	weight_data_long <- melt(bg_weight, id.vars = id_cols, measure.vars = DEMO_COLS, value.name ='demo_weighted_dist' , variable.name = "demographic")

	#merge the two datasets to get one with both demo_pop and demo_weighted_distance columns
	bg_demo_weight <- merge(demo_data_long, weight_data_long, by = c('bg_id','config_set', 'config_name', 'descriptor', 'demographic'))

	#create a demographic average distance column
	bg_demo_weight <- bg_demo_weight[ , demo_avg_dist := demo_weighted_dist/demo_pop]

	#get block group level map name
	bg_map_file <- get_map_file(location, block_flag = FALSE)
	#extract columns
	bg_map_data<- process_maps(bg_map_file)
	#merge.
	#note, area not aggregated above but taken from bg_map
	bg_result_with_geom <- merge(bg_demo_weight, bg_map_data, by.y = c('GEOID20'), by.x = c('bg_id'))
	
	return(bg_result_with_geom)
}



###########
#Prep map data for later mapping
#add location to residence data, aggregate to block grouplevel,
# 	merge with polling locations and split by config_name
###########
extract_unique_location <- function(df){
	#extract location from data
	location <- unique(df$location)
	if(length(location) >1){
		stop(paste('Multiple locations in this result data from config set', df$config_set, 'with config name', df$config_name))
		}
	return(location)
}

merge_bg_demo_shp_data <- function(result_df){
	#Merge map and result_df at block group level
	#Note: This does it differently than before
	#(see make_or_load_maps_old, where, if map_type = boundary, 
	#the contained in data was
	#used preferentially. Here, we use the appropriate block data
	#in each case))

	location <- extract_unique_location(result_df)
	
	#merge demo and geom data
	bg_demo_shape <- bg_result_geom(location, result_df)

	#add location back in 
	bg_demo_shape <- bg_demo_shape[, location := location]

	#get unique polling coordinates
	result_polls_coords <- result_df[ , .(dest_lat, dest_lon, id_orig, dest_type)
								   ][ , bg_id:= gsub('.{3}$', '', id_orig)][ , id_orig:=NULL]
	result_polls_coords <- unique(result_polls_coords)

	#merge in polling data
	bg_demo_shape_dest <- merge(bg_demo_shape, result_polls_coords, by = c('bg_id'), all.x = TRUE, allow.cartesian = TRUE)
	return(bg_demo_shape_dest)
}
	

prepare_outputs_for_bg_maps <- function(result_dt){

	result_data <- copy(result_dt)
	#if input NULL, and HISTORIC_FLAG return NULL 
	if(check_historic_flag(result_data)){
		return(NULL)
	}

	#split by config_name
	result_list <- split(result_data, result_data$config_name)

	#merge shape data and aggregate to bg
	result_list <- lapply(result_list, function(df)merge_bg_demo_shp_data(df))

	return(result_list)
}

prepare_outputs_for_precinct_maps <- function(result_dt){

	result_data <- copy(result_dt)
	#if input NULL, and HISTORIC_FLAG return NULL 
	if(check_historic_flag(result_data)){
		return(NULL)
	}

	#split by config_name
	result_list <- split(result_data, result_data$config_name)

	#extract unique location
	location_list <- lapply(result_list, function(df) extract_unique_location(df))

	#merge shape data
	result_with_geom <- mapply(function(location, df)results_with_area_geom(location, df), location_list, result_list, SIMPLIFY = FALSE)

	#make map data an sf object
	sf_list <- lapply(result_with_geom, st_as_sf)
	
	return(sf_list)
}


###########
#Calculate min and max distance for a dataframe
###########

distance_bounds <- function(df){
	#calculate the min and max average distances traveled by census block for maps by location

	prepped_df <- copy(df)
	# pull out min and max average distances by location
	bound_dt <- prepped_df[, .(min_avg_dist = min(avg_dist), max_avg_dist = max(avg_dist)), by = location]

	# check for missing data
	if (any(sapply(bound_dt, anyNA))){
    warning('Some location does not have a min or max average distance for mapping')}

	# pull out global bounds
	global_max <- max(bound_dt$max_avg_dist)
	global_min <- max(bound_dt$min_avg_dist)
	color_bounds <- list(global_min, global_max)
	return(color_bounds)
}


###############
#Make block group maps
###############

make_bg_maps <-function(prepped_data, demo_str = 'population', driving_flag = DRIVING_FLAG, log_flag = LOG_FLAG, color_bounds = global_color_bounds){ 
	#use aggregated result data to color the map by distance to matched location, for population at large
	#and plots the polling locations
	
	#transform for prepped data for mapping
	prepped_demo <- prepped_data[demographic == demo_str, ]
	bg_demo_sf <- st_as_sf(prepped_demo)

	#make maps labels based on flags
	flag_strs <- make_flag_strs(driving_flag, log_flag)
	
	title_str = paste0('Average', flag_strs$driving_str, 'distance to poll (', flag_strs$log_str, 'm)')
	fill_str = paste0('Avg distance (', flag_strs$log_str, 'm)')

	county = gsub('.{3}$','', unique(prepped_data$location))
	descriptor = paste(county, unique(prepped_data$descriptor), sep ='_')
	
	#make maps
	#color by bg avg distance
	plotted <- ggplot() +
		geom_sf(data = bg_demo_sf, aes(fill = demo_avg_dist)) +
		scale_fill_gradient(low='white', high='darkgreen', limits = c(color_bounds[[1]], color_bounds[[2]]), name = fill_str)
	#place polling locations
	plotted = plotted +
		geom_point(data = bg_demo_sf, aes(x = dest_lon, y = dest_lat, color = dest_type))+
		scale_color_manual(breaks = c('polling', 'potential', 'bg_centroid'), values = c('red', 'black', 'dimgrey'), name = 'Poll Type') +  xlab('') + ylab('')
	#add title
	plotted = plotted + ggtitle(title_str, paste('Block group map', 'of', gsub('_', ' ', descriptor) ))

	#write to file
	graph_file_path = paste0('distance_', descriptor, '_','polls.png')
	add_graph_to_graph_file_manifest(graph_file_path)
	ggsave(graph_file_path, plotted)
}

make_demo_dist_map <-function(prepped_data, demo_str, driving_flag = DRIVING_FLAG, log_flag = LOG_FLAG, color_bounds = global_color_bounds){
	#use demographic residence_distances to put a dot in  the map colored by distance and sized by population
	
	#transform for prepped data for mapping
	prepped_demo <- prepped_data[demographic == demo_str, ]
	#prepped_data <- unique(prepped_demo)
	bg_demo_sf <- st_as_sf(prepped_demo)

	#change lat/lon to numeric
	bg_demo_sf$INTPTLON20 <- as.numeric(bg_demo_sf$INTPTLON20)
	bg_demo_sf$INTPTLAT20 <- as.numeric(bg_demo_sf$INTPTLAT20)

	
	#plot map with a point at the centroid, colored by distance, sized by size
	#set names
	flag_strs <- make_flag_strs(driving_flag, log_flag)

	title_str = paste0('Average', flag_strs$driving_str, 'distance to poll (', flag_strs$log_str, 'm)')
	color_str = paste0('Avg distance (', flag_strs$log_str, 'm)')

	county = gsub('.{3}$','', unique(prepped_data$location))
	descriptor = paste(county, unique(prepped_data$descriptor), sep ='_')
	
	#size limits (This should be the block group with greatest total population
	#for ease of comparison across demographics)
	max_pop <- max(prepped_data$demo_pop)

	plotted <- ggplot() +
		geom_sf(data = bg_demo_sf) +
		geom_point(data = bg_demo_sf, aes(x = INTPTLON20, y = INTPTLAT20, size= demo_pop, color = demo_avg_dist)) +
		scale_color_gradient(low='white', high='darkgreen', limits = c(color_bounds[[1]], color_bounds[[2]]), name = color_str) +
		labs(size = paste(demographic_legend_dict[demo_str], 'population') ) +
		xlab('') + ylab('') + scale_size(limits= c(0, max_pop)) +
		ggtitle(paste(demographic_legend_dict[demo_str], title_str), paste('Block groups in', gsub('_', ' ', descriptor)))
	
	#write to file
	graph_file_path = paste0(demo_str, '_','pop_and_dist','_',descriptor, '_','polls.png')
	add_graph_to_graph_file_manifest(graph_file_path)
	ggsave(graph_file_path, plotted)

}

#############
#precinct map
#NOTE: done at block level
#############
make_precinct_map_no_people <- function(df_sf){

	#make map where blocks with no people are in grey
	plotted <- ggplot() +	
		geom_sf(data = df_sf, aes(fill = id_dest), show.legend = FALSE)+
        geom_point(data = df_sf, aes(x = dest_lon, y = dest_lat), show.legend = FALSE)
	
	location <- unique(df_sf$location)
	descriptor <- unique(df_sf$location)

	browser()
	#write to file
	graph_file_path = paste0(location, '_','precinct','_',descriptor, '_','indicate_0_population.png')
	add_graph_to_graph_file_manifest(graph_file_path)
	ggsave(graph_file_path, plotted)
}

make_precinct_map <- function(df_sf){

	#separate out populated and unpopulated blocks
	df_sf_pop <- df_sf[!is.na(df_sf$id_dest), ]
	df_sf_unpop <- df_sf[is.na(df_sf$id_dest), ]

	#Group by assigned dest.
	precincts_sf_pop <- df_sf_pop %>% group_by(id_dest, descriptor, dest_lat, dest_lon) %>% summarize(precinct_geom = st_union(geometry))

	#adjust unpop data to match pop data
	names(df_sf_unpop)[names(df_sf_unpop) == 'geometry'] <- 'precinct_geom'
	st_geometry(df_sf_unpop) <- 'precinct_geom'
	df_sf_unpop <- df_sf_unpop[, names(precincts_sf_pop)]

	#associate the unpopulated / unassigned ccs to the closests assigned feature
	unpop_join <- st_join(df_sf_unpop, precincts_sf_pop, join=st_nearest_feature)
	unpop_narrow <- unpop_join[ , !(grepl('\\.x', names(unpop_join)))]
	names(unpop_narrow) <- gsub('\\.y', '',names(unpop_narrow))

	#combine populated and unpopulated data
	precincts_sf_all <- rbind(unpop_narrow, precincts_sf_pop) %>% group_by(id_dest, descriptor, dest_lat, dest_lon) %>% summarize(precinct_geom = st_union(precinct_geom))

	#drop crumbs
	area_thresh <- units::set_units(2, km^2)
	precincts_sf_valid <- st_make_valid(precincts_sf_all)
	precincts_sf_clean <- precincts_sf_valid %>% st_buffer(50)
	plotted<- ggplot() +	
		geom_sf(data = precincts_sf_valid, aes(fill = id_dest), show.legend = FALSE)+
			geom_point(data = precincts_sf_all, aes(x = dest_lon, y = dest_lat), show.legend = FALSE)

	location <- unique(df$location)
	descriptor <- unique(df_sf$location)
	#write to file
	graph_file_path = paste0(location, '_','precinct','_',descriptor,'.png')
	add_graph_to_graph_file_manifest(graph_file_path)
	ggsave(graph_file_path, plotted)

}

###################

make_or_load_maps_old <- function(location, map_type, demographic = 'population'){
	#Note: No longer supports cartograms. 
	#All maps made on the fly.
	#map data no longer stored

	#makes the map by loading the census shape and demographic data
	#and merging.
	#1. set a name for a map
	#2. make map
	#2a. get block group level demographics
	#2b. get block group shape files
	#2c. merge shape file with demographics, assign projection
	#2d. make map

	#1. name the desired map
	if (map_type == 'map'){
		map_name<- paste0(location, "_", map_type, '.shp')
	} else if (map_type == 'boundries'){
		map_name<- paste0(location, "_", map_type, '.shp')
	} else{
		stop('map_type must be either map, or boundries')
	}

	#2. Make map
	#2a. get block group demographics
	if (map_type == 'boundries') { 
		#associate block group demographics based on only on blocks included in boundary

		#get block level demographics
		block_demo <- process_demographics(paste0(here(), '/datasets/census/redistricting/', location))
		#drop columns that cannot be aggregated (aren't numeric)
		demo_names <- names(block_demo)[sapply(block_demo,is.integer) ==TRUE]
		#aggregate up to block group level
		bg_demo <- block_demo[ , Geography := gsub('.{3}$', '', Geography)
							][ ,`Geographic Area Name` := gsub('^.{12}', '',`Geographic Area Name` )
							][ , lapply(.SD, sum), by = c('Geography','Geographic Area Name'), .SDcols = demo_names]
	} else { # get demographics from existing block groups data
		bg_demo <- process_demographics(paste0(here(), '/datasets/census/redistricting/', location, "/block group demographics"))
	}
	#2b. get shape file
	#Block group shape files
	if (map_type == 'boundries') { #use the Intersecting data for both maps
		bg_shape_file <- list.files(paste0(here(), '/datasets/census/tiger/',gsub('Contained_in', 'Intersecting', location) ), pattern = 'bg20.shp$')
		#get processed map data
		map_bg_dt <- process_maps(paste0(here(), '/datasets/census/tiger/', gsub('Contained_in', 'Intersecting', location) , '/', bg_shape_file))
	} else {
		bg_shape_file <- list.files(paste0(here(), '/datasets/census/tiger/', location ), pattern = 'bg20.shp$')
		#get processed map data
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
	#4. make map 
	map <- st_transform(bg_demo_sf, projection)	
	return(map)
}



