library(data.table)
library(ggplot2)
library(lubridate)
library(mapview)
library(sf)
library(cartogram)
library(broom)

#########
#change directory for map data
#this is data from Tiger, 2020
#########
setwd("~")
setwd("../../Equitable-Polling-Locations/datasets/census/tiger/Gwinnett_GA/") 

process_maps <- function(file_name){
    #read in map data as data table
    map <-st_read(file_name)
    map_dt <- as.data.table(map)
    #add column for total area, keep only id, area, shape
    map_dt <- map_dt[ , AREA20 := ALAND20 + AWATER20
				][ , .(GEOID20, AREA20, geometry)]
    
    return (map_dt)
}

#Block group shape files
map_bg_dt <- process_maps("tl_2020_13135_bg20.shp")
#make sf type
map_bg_sf <- st_as_sf(map_bg_dt)

#ggplot() +
#  geom_sf(data = maps_bg_sf)

#Block shape files
#maps_block_dt <- process_maps("tl_2020_13135_tabblock20.shp")
#make sf type
#maps_block_sf <- st_as_sf(maps_block_dt)

#ggplot() +
#  geom_sf(data = maps_block_sf)

#########
#get populations
#########
setwd("~")
setwd("../../Equitable-Polling-Locations/datasets/census/redistricting/Gwinnett_GA") 

process_demographics <-function(folder_name){
#Take P3 and P4 tables from the indicated folder and makes a combined demographics table

    #read in demographics
    P4 = paste(folder_name, 'DECENNIALPL2020.P4-Data.csv', sep = '/')
    P3 = paste(folder_name, 'DECENNIALPL2020.P3-Data.csv', sep = '/')
    P3_demo <- fread(P3, skip = 1, header = T)
    P4_demo <- fread(P4, skip = 1, header = T)
   
    #clean up data
    #select "Geography" "Geographic Area Name" and demographic columns
    P3_demo<-P3_demo[,c(1:3, 7, 9, 11, 13, 15, 17, 19)]
    P4_demo<-P4_demo[,c(1:3, 5, 7)]
    #Change Population column name
    setnames(P3_demo, names(P3_demo)[3:10], c("Population", "White", "Black", "Native", "Asian", "PacificIslander", "Other", "Multiple"))
    setnames(P4_demo, names(P4_demo)[3:5], c("Population", "Hispanic", "NonHispanic")
    )
    #merge to get all demographics
    demo = merge(P3_demo, P4_demo, by = c('Geography', 'Geographic Area Name', 'Population'), all = TRUE)
    #Change geography tag to match mapping data
    demo = demo[, Geography := sub(".*US", '', Geography)]
}



#block group demographics
bg_demo <- process_demographics("block group demographics")

#block demographics
block_demo <- process_demographics('.')

#########
#make block level cartogram
#########

bg_demo_shape <- merge(map_bg_dt, bg_demo, by.x = c('GEOID20'), by.y = c('Geography'))
bg_demo_sf <- st_as_sf(bg_demo_shape)
bg_demo_merc <- st_transform(bg_demo_sf, 3857)
cartogram <- cartogram_cont(bg_demo_merc, "Population", itermax = 50, maxSizeError = 1.02)

#########
#Get model output
#########
setwd("~")
setwd("../../Equitable-Polling-Locations/Gwinnett_GA_results") 

res_dist_list = list.files()[grepl('residence_distances', list.files())]
res_dist_list = res_dist_list[!grepl('full', res_dist_list)]
#to_map = res_dist_list[1]

#If precincts want to be mapped as well
#result_list = list.files()[grepl('result', list.files())]
#result_list = result_list[!grepl('full', res_dist_list)]
#result = result_list[1]

make_bg_maps <-function(file_to_map, map_type){
	#read in results to map
	res_dist_df <- fread(file_to_map)
	res_dist_df <- res_dist_df[ , id_orig := as.character(id_orig)
		][ , BG_Geography := gsub('.{3}$', '', id_orig)]
	
	#extract demographics from map
	#must do this way because map is an sf object, not a data.table
	if (map_type == 'cartogram'){
		map_demo = cartogram
	}else if (map_type == 'map'){
		map_demo = bg_demo_merc
	}else {map_demo = other}

	block_geog <- data.table(GEOID20 = map_demo$GEOID20)
	
	geom_cols <- c('GEOID20', 'geometry')
	map_sf <- map_demo[, geom_cols]
	
	#merge demographics and distances
	demo_dist <- merge(block_geog, 
		res_dist_df[demographic == 'population', .(BG_Geography, demo_pop, weighted_dist)], 
		by.x = c("GEOID20"), by.y = c("BG_Geography"), all.y = T)
	
	#aggregrage block to groups
	#summary_cols = names(demo_dist)[!names(demo_dist) %in% c('AREA20', 
	#				'Geographic Area Name')] 
	bg_demo_dist <- demo_dist[ , .(demo_pop = sum(demo_pop),
						weighted_dist = sum(weighted_dist)), by = GEOID20
					][ , avg_dist := weighted_dist/demo_pop]
		
	#combine with demo_dist with map
	demo_dist_shape<- merge(map_sf, bg_demo_dist, all = T)	
	
	#make maps
	plotted <- ggplot() +
		geom_sf(data = demo_dist_shape, aes(fill = avg_dist)) + 
		scale_fill_gradient(high='white', low='darkgreen', limits = c(100, 15000))  
		
	#write to file
	descriptor = gsub(".*config_(.*)_res.*", "\\1", file_to_map)
	ggsave(paste0('../result analysis/', map_type, '_',descriptor, '.png'), plotted)
	}
sapply(res_dist_list, function(x)make_bg_maps(x, 'cartogram'))
sapply(res_dist_list, function(x)make_bg_maps(x, 'map'))



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



