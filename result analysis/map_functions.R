library(data.table)
library(ggplot2)
library(lubridate)
#library(mapview)
library(sf)
library(cartogram)
#library(broom)

source('result analysis/graph_functions.R')


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
    setnames(P4_demo, names(P4_demo)[3:4], c("hispanic", 'non-hispanic'))
    #merge to get all demographics
    demo = merge(P3_demo, P4_demo, by = c('Geography', 'Geographic Area Name'), all = TRUE)
    #Change geography tag to match mapping data
    demo = demo[, Geography := sub(".*US", '', Geography)]
	#drop empty block groups
	demo = demo[population >0, ]
}

process_residence <- function(file_name, demo_str, result_folder){
	#read in residence data from the model output, which is at the block 
	#level, and aggregate it at the block group level,
	#selecting for the given demographic

	#read in residence data set
	if (!grepl('residence_distances', file_name)){
		stop('file_name not a residence_distances file')
	}
	#read in data
	res_dist_df <- fread(paste0(here(), '/',result_folder, '/', file_name))

	#the last 3 digits are the block, remove these for block group
	#GEOID20 is the BG column name from the census
	res_dist_df <- res_dist_df[ , id_orig := as.character(id_orig)
		][ , GEOID20 := gsub('.{3}$', '', id_orig)]
	
	#aggregate by block group
	bg_res_dist <- res_dist_df[ , .(demo_pop = sum(demo_pop),weighted_dist = sum(weighted_dist)), 
										by = c('GEOID20', 'demographic')][ , avg_dist := weighted_dist/demo_pop]

	#select demographic
	bg_res_demo_dist <- bg_res_dist[demographic == demo_str, ]
	return(bg_res_demo_dist)
}

distance_bounds <- function(location, config_folder){
	#calculate the min and max average distances traveled by census block for maps

	#get full residence data
	residence_df<- combine_results(location, config_folder, 'residence_distances')
	residence_df <- residence_df[demographic == 'population', ]
	min_avg_dist <- min(residence_df$avg_dist)
	max_avg_dist <- max(residence_df$avg_dist)
	return(list(min_avg_dist, max_avg_dist))
}

make_or_load_maps <- function(location, map_type, demographic = 'population'){
	#checks if the desired map .csv already exists, and load it if it does
	#else, makes the map by loading the census shape and demographic data
	#and merging.

	#name the desired map
	if (map_type == 'cartogram'){
		map_name<- paste0(location, "_", map_type, '_', demographic, '.shp')
	} else if (map_type == 'map'){
		map_name<- paste0(location, "_", map_type, '.shp')
	} else{
		stop('map_type must be either map or cartogram')
	}
	map_folder <- 'result analysis/map work'
	#load if it exists, else make
	if (file.exists(file.path(here(), map_folder, map_name))){
		map <- st_read(file.path(here(), map_folder, map_name))
		#name resetting needed because of st_write truncating names
		names(map) <- c("GEOID20", "AREA20", "INTPTLAT20", "INTPTLON20", "Geographic Area Name", "population", "white", "black", "native", "asian", "pacific_islander", "other", "multiple_races", "hispanic", "non-hispanic", "geometry")
	} else {
		#block group demographics
		bg_demo <- process_demographics(paste0(here(), '/datasets/census/redistricting/', location, "/block group demographics"))

		#get shape file
		#Block group shape files
		bg_shape_file <- list.files(paste0(here(), '/datasets/census/tiger/', location ), pattern = 'bg20.shp$')
		#get map data
		map_bg_dt <- process_maps(paste0(here(), '/datasets/census/tiger/', location, '/', bg_shape_file))

		#merge the bg shape dt with the bg demo dt
		bg_demo_shape <- merge(map_bg_dt, bg_demo, by.x = c('GEOID20'), by.y = c('Geography'))
		#make it an sf object for mapping
		bg_demo_sf <- st_as_sf(bg_demo_shape)
		#assign it a projection
		if (map_type == 'map'){ 
			projection = 4326 #must use this projection if you want to add points to map
		} else {
			projection = 3857 #correct projection for merc
		}
		#make map and write to file
		map <- st_transform(bg_demo_sf, projection)
		if (map_type == 'cartogram'){
			map <- cartogram_cont(map, demographic, itermax = 200, maxSizeError = 1.02)
			
		}
		st_write(map, file.path(here(), map_folder, map_name))
	}
	return(map)
}

make_bg_maps <-function(config_folder, file_to_map, map_type, result_folder_name = result_folder, this_location = location, demo_str = 'population'){
	#read in a residence_distance file from the correct config_folder, combine this and use it to color the map by distance to matched location, for the indicated demographic
	#If the map type is "map", then also plot the polling locations

	#read in block level data and aggregate to block group level
	res_dist_demo <- process_residence(file_to_map, demo_str, result_folder_name)

	#extract demographics from map
	#must do this way because map is an sf object, not a data.table
	if (map_type == 'cartogram'){
		map_demo = make_or_load_maps(this_location, 'cartogram', demo_str)
		map_name = paste('distance', demo_str, map_type, sep = '_')
	}else if (map_type == 'map'){
		map_demo = make_or_load_maps(this_location, 'map')
		map_name = paste('distance', map_type, sep = '_')
		#in this case, also put in the precincts
		ev_df_name <-sub('residence_distances', 'result', file_to_map)
		result_df <- fread(paste0(here(), '/',result_folder_name, '/', ev_df_name))
		ev_locs <- result_df[ , .(long = unique(dest_lon), lat = unique(dest_lat), type = unique(dest_type)), by = id_dest]
	} else {
		stop('map_type must be either map or cartogram')
	}

	#combine with res_dist_demo with map
	geom_cols <- c('GEOID20', 'geometry')
	map_sf <- map_demo[, geom_cols]
	demo_dist_shape<- merge(map_sf, res_dist_demo, all = T)	
	
	#make maps
	if (grepl('driving', config_folder)){
		title_str = 'Average driving distance to poll (m)'
		fill_str = 'Avg driving distance (m)'
	} else{
		title_str = 'Average distance to poll (m)'
		fill_str = 'Avg straight line distance (m)'
	}

	county = gsub('.{3}$','',this_location)
	numeric_label = str_extract(file_to_map, '[0-9]+')
	descriptor = paste(county, numeric_label, sep ='_')
	plotted <- ggplot() +
		geom_sf(data = demo_dist_shape, aes(fill = avg_dist)) + 
		scale_fill_gradient(low='white', high='darkgreen', limits = c(color_bounds[[1]], color_bounds[[2]]), name = fill_str) 
	if (map_type == 'map'){
		plotted = plotted + 
		geom_point(data = ev_locs, aes(x = long, y = lat, color = type))+ 
		scale_color_manual(breaks = c('polling', 'potential', 'bg_centroid'), values = c('red', 'black', 'dimgrey'), name = 'Poll Type') +  xlab('') + ylab('') 
	} else{ 
		plotted = plotted + theme(axis.text.x=element_blank(), axis.text.y=element_blank(), axis.ticks = element_blank())
	}
	plotted = plotted + ggtitle(title_str, paste('Block group', map_type , 'of', gsub('_', ' ', descriptor) ))

	if (grepl('driving', config_folder)){
	plotted <- plotted #+ labs(fill = 'Avg driving distance (m)')
	} else {
		plotted <- plotted #+ labs(fill = 'Avg straight line distance (m)')
	}

	#write to file
	descriptor = gsub(".*configs.(.*)_res.*", "\\1", file_to_map)
	num_polls <- str_extract(descriptor, '[0,-9]+')
	ggsave(paste0(here(), '/', plot_folder, '/',map_name, '_',descriptor, '_','polls.png'), plotted)
	}

make_demo_dist_map <-function(config_folder, file_to_map, demo_str, result_folder_name = result_folder, this_location = location){

	#read in block level data and aggregate to block group level
	res_dist_df <- process_residence(file_to_map, demo_str, result_folder_name)
	#get map
	map_demo <- make_or_load_maps(this_location, 'map')
	geom_cols <- c('GEOID20', 'INTPTLON20', 'INTPTLAT20', 'geometry')
	map_sf <- map_demo[, geom_cols]
	#change lat/lon to numeric
	map_sf$INTPTLON20 <- as.numeric(map_sf$INTPTLON20)
	map_sf$INTPTLAT20 <- as.numeric(map_sf$INTPTLAT20)

	#merge
	demo_dist_shape<- merge(map_sf, res_dist_df, all = T)

	#plot map with a point at the centroid, colored by distance, sized by size
	#set names
	if (grepl('driving', config_folder)){
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
	pop_dist_df <- process_residence(file_to_map, 'population', result_folder_name)
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



