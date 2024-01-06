#######
#Change directory
#######
setwd(here())

#######
#source functions
#######
source('result analysis/map_functions.R')
source('result analysis/graph_functions.R')

#######
#Set Constants
#######
#Location must be part of config folder string

location = 'DeKalb_GA'
config_folder = 'DeKalb_GA_original_configs'

#######
#Check that location and folders valid
#######

check_location_valid(location, config_folder)
check_config_folder_valid(config_folder)

#########
#get map data
#change directory first
#this is data from Tiger, 2020
#########
setwd(paste0(here(), '/datasets/census/tiger/', location ))

#Block group shape files
bg_shape_index <- which(grepl('bg20.shp$', list.files()))
bg_shape_file <- list.files()[bg_shape_index]
#get map data
map_bg_dt <- process_maps(bg_shape_file)

#########
#get populations
#again, this is from redistricting 2020
#########
setwd(paste0(here(), '/datasets/census/redistricting/', location ))

#block group demographics
bg_demo <- process_demographics("block group demographics")

#block demographics
#block_demo <- process_demographics('.')

#########
#make block level cartogram
#########

#merge the bg shape dt with the bg demo dt
bg_demo_shape <- merge(map_bg_dt, bg_demo, by.x = c('GEOID20'), by.y = c('Geography'))
#make it an sf object for mapping
bg_demo_sf <- st_as_sf(bg_demo_shape)
#assign it a projection
bg_demo_flat <- st_transform(bg_demo_sf, 4326) #must use this projection if you want to add points to map
#make it into a cartogram
bg_demo_merc <- st_transform(bg_demo_sf, 3857)
cartogram <- cartogram_cont(bg_demo_merc, "Population", itermax = 50, maxSizeError = 1.02)

#########
#Make maps and cartograms
#########
#change directory to get results
result_folder = paste(location, 'results', sep = '_')
setwd(paste0(here(), '/',result_folder))

#get all file names the result_folder with the strings config_folder and 'residence_distances'
res_dist_list = list.files()[grepl('residence_distances', list.files())]
res_dist_list = res_dist_list[grepl(config_folder, res_dist_list)]


#check if relevant directory existss
plot_folder = paste0('result analysis/', config_folder)
if (!file.exists(file.path(here(), plot_folder))){
    dir.create(file.path(here(), plot_folder))
}

sapply(res_dist_list, function(x)make_bg_maps(x, 'cartogram'))
sapply(res_dist_list, function(x)make_bg_maps(x, 'map'))

