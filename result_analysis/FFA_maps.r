#######
#NOTE: this file is deprecated. It is not compatible with the new graph_functions
#structure that reads data from the config files
#######
library(here)
#######
#Change directory
#######
setwd(here())

#######
#source functions
#######
source('result_analysis/map_functions.R')
source('result_analysis/graph_functions.R')

#######
#Set Constants
#######
#Location must be part of config folder string


LOCATION = 'Chatham_County_GA'
CONFIG_FOLDER = 'Chatham_County_GA_original_configs'


#original_locations = paste(LOCATION, 'original', 'configs', sep = '_')
#CONFIG_FOLDER = original_locations
#######
#Check that location and folders valid
#######

#Does the config folder exist?
check_config_folder_valid(CONFIG_FOLDER)
#Does the config folder contain files associated to the location
#check_location_valid(LOCATION, CONFIG_FOLDER)

#########
#Set up maps and cartograms
#########
#set result folder
result_folder = paste(LOCATION, 'results', sep = '_')

#get all file names the result_folder with the strings config_folder and 'residence_distances'
res_dist_list = list.files(result_folder)[grepl('residence_distances', list.files(result_folder))]
res_dist_list = res_dist_list[grepl(CONFIG_FOLDER, res_dist_list)]


#get avg distance bounds for map coloring
color_bounds <- distance_bounds(LOCATION, CONFIG_FOLDER)


#########
#Make maps and cartograms
#########
#check if relevant directory exists
plot_folder = paste0('result_analysis/', CONFIG_FOLDER)
if (!file.exists(file.path(here(), plot_folder))){
    dir.create(file.path(here(), plot_folder))
}

#Choosing not to do cartograms because of convergence difficulties
#sapply(res_dist_list, function(x)make_bg_maps(x, 'cartogram'))
sapply(res_dist_list, function(x)make_bg_maps(CONFIG_FOLDER, x, 'boundries'))
sapply(res_dist_list, function(x)make_demo_dist_map(CONFIG_FOLDER, x, 'black',map_type = 'boundries'))
sapply(res_dist_list, function(x)make_demo_dist_map(CONFIG_FOLDER, x, 'white',map_type = 'boundries'))
sapply(res_dist_list, function(x)make_demo_dist_map(CONFIG_FOLDER, x, 'hispanic',map_type = 'boundries'))

