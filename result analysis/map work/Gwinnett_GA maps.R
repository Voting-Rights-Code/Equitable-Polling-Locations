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
maps_bg_dt <- process_maps("tl_2020_13135_bg20.shp")
#make sf type
maps_bg_sf <- st_as_sf(map_bg_dt)

ggplot() +
  geom_sf(data = maps_bg_sf)

#Block shape files
maps_block_dt <- process_maps("tl_2020_13135_tabblock20.shp")
#make sf type
maps_block_sf <- st_as_sf(maps_block_dt)

ggplot() +
  geom_sf(data = maps_block_sf)

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

make_bg_maps <-function(to_map){
	#read in results to map
	res_dist_df <- fread(to_map, drop = 'V1')
	res_dist_df <- res_dist_df[ , id_orig := as.character(id_orig)]
	
	#Removed for now, add in an argument (result) for precinct data
	#result_df <- fread(result, drop = 'V1')
	#result_df <- result_df[ , id_orig := as.character(id_orig)]
	#precincts <- result_df[ , .(dest_lat = unique(dest_lat), 
					#dest_lon = unique(dest_lon)), by = id_dest]
	
	
	#combine with existing data
	distance_demo <- merge(block_demo, 
		res_dist_df[demographic == 'population', .(id_orig, weighted_dist)], 
		by.x = c("Geography"), by.y = c("id_orig"))

	distance_demo <- distance_demo[ , BG_Geography := gsub('.{3}$', '', Geography)]

	summary_cols = names(distance_demo)[!names(distance_demo) %in% c('Geography', 
					'Geographic Area Name')] 
	bg_distance_demo <- distance_demo[ , ..summary_cols
		][ , lapply(.SD, sum), by = BG_Geography
		][ , avg_dist := weighted_dist/Population]

	dist_demo_shape <- merge(bg_distance_demo, maps_bg_dt, by.x = c("BG_Geography"), 
			by.y = c("GEOID20"))
	
	#change types for mapping
	dist_demo_sf <- st_as_sf(dist_demo_shape)
	dist_demo_merc <- st_transform(dist_demo_sf, 3857)

	#precincts_sf<- st_as_sf(precincts, coords = c('dest_lon', 'dest_lat'), crs = 4326)
	#precincts_merc <- st_transform(precincts_sf, 3857)

	
	#make cartogram
	cartogram <- cartogram_cont(dist_demo_merc, "Population")
	
	#make maps
	warped = ggplot() +
  		geom_sf(data = cartogram, aes(fill = avg_dist)) 

	#can add precinct data onto the unwarped map, but no paralell for cartogram
	straight = ggplot() +
  		geom_sf(data = dist_demo_merc, aes(fill = avg_dist)) #+
		#geom_sf(data = precincts_sf, aes(colour = id_dest), show.legend = FALSE)+
		#scale_color_manual(values = rep('red', nrow(precincts_sf)))


	#write to file
	descriptor = gsub(".*config_(.*)_res.*", "\\1", to_map)
	ggsave(paste0('../result analysis/cartogram_',descriptor, '.png'), warped)
	ggsave(paste0('../result analysis/map_',descriptor, '.png'), straight)
	}


sapply(res_dist_list, make_bg_maps)


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



