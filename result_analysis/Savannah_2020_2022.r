library(here)

#######
#Change directory
#######
setwd(here())

#######
#source functions
#######

source('result_analysis/graph_functions.R')
source('result_analysis/map_functions.R')

#######
#Set Constants
#######

#Basic constants for analysis
#LOCATION must be either a string or list of strings
#CONFIG_FOLDER must be a string

LOCATION = 'Contained_in_Savannah_City_of_GA'
CONFIG_FOLDER = 'Contained_in_Savannah_City_of_GA_original_configs'

POTENTIAL_CONFIG_FOLDER = 'Contained_in_Savannah_City_of_GA_no_bg_school_configs'


#######
#Check that location and folders valid
#this also ensures that you are in the right folder to read data
#######

#Does the config folder exist?
check_config_folder_valid(CONFIG_FOLDER)
#Does the config folder contain files associated to the location
check_location_valid(LOCATION, CONFIG_FOLDER)

#Does the config folder exist?
check_config_folder_valid(POTENTIAL_CONFIG_FOLDER)
#Does the config folder contain files associated to the location
check_location_valid(LOCATION, POTENTIAL_CONFIG_FOLDER)


#######
#Read in data
#Run this for each of the folders under consideration
#Recall, output of form: list(ede_df, precinct_df, residence_df, result_df)
#######
#driving flag
config_list <- c(CONFIG_FOLDER, POTENTIAL_CONFIG_FOLDER)
DRIVING_FLAG <- set_global_driving_flag(config_list)

config_df_list <- read_result_data(LOCATION, CONFIG_FOLDER)
#config_ede_df<- config_df_list[[1]]
#config_precinct_df<- config_df_list[[2]]
#config_residence_df<- config_df_list[[3]]
#config_result_df<- config_df_list[[4]]

potential_config_df_list <- read_result_data(LOCATION, POTENTIAL_CONFIG_FOLDER)

#########
#Set up maps and cartograms
#########
#set result folder to read data from
result_folder = paste(LOCATION, 'results', sep = '_')

#get all file names the result_folder with the strings config_folder and 'residence_distances'
res_dist_list = list.files(result_folder)[grepl('residence_distances', list.files(result_folder))]
orig_res_dist_list = res_dist_list[grepl(CONFIG_FOLDER, res_dist_list)]
potential_res_dist_list = res_dist_list[grepl(POTENTIAL_CONFIG_FOLDER, res_dist_list)]

#get avg distance bounds for map coloring
orig_color_bounds <- distance_bounds(LOCATION, CONFIG_FOLDER)
potential_color_bounds <- distance_bounds(LOCATION, POTENTIAL_CONFIG_FOLDER)
global_min <- min(orig_color_bounds[[1]], potential_color_bounds[[1]])
global_max <- max(orig_color_bounds[[2]], potential_color_bounds[[2]])
color_bounds <- list(global_min, global_max)

#######
#Plot data
#######
plot_folder = paste0('result_analysis/', CONFIG_FOLDER)
if (file.exists(file.path(here(), plot_folder))){
    setwd(file.path(here(), plot_folder))
} else{
    dir.create(file.path(here(), plot_folder))
    setwd(file.path(here(), plot_folder))
}

###graphs####

#Add percent population to data ede data for graph scaling for all general config folder and orig
pop_scaled_edes <- ede_with_pop(config_df_list)
#Plot the edes for all runs in original_location and equivalent optimization runs by demographic
plot_historic_edes(pop_scaled_edes, suffix = 'pop_scaled')

plot_precinct_persistence(config_df_list[[2]])

####maps####
sapply(orig_res_dist_list, function(x)make_bg_maps(x, 'boundries'))
sapply(orig_res_dist_list, function(x)make_demo_dist_map(x, 'black', map_type = 'boundries'))
sapply(orig_res_dist_list, function(x)make_demo_dist_map(x, 'white', map_type = 'boundries'))
sapply(orig_res_dist_list, function(x)make_demo_dist_map(x, 'hispanic', map_type = 'boundries'))
sapply(orig_res_dist_list, function(x)make_demo_dist_map(x, 'asian', map_type = 'boundries'))
sapply(orig_res_dist_list, function(x)make_demo_dist_map(x, 'population', map_type = 'boundries'))

sapply(orig_res_dist_list, function(x)make_bg_maps(x, 'map'))
#sapply(orig_res_dist_list, function(x)make_demo_dist_map(CONFIG_FOLDER, x, 'black', map_type = 'map'))
#sapply(orig_res_dist_list, function(x)make_demo_dist_map(CONFIG_FOLDER, x, 'white', map_type = 'map'))
#sapply(orig_res_dist_list, function(x)make_demo_dist_map(CONFIG_FOLDER, x, 'hispanic', map_type = 'map'))
#sapply(orig_res_dist_list, function(x)make_demo_dist_map(CONFIG_FOLDER, x, 'asian', map_type = 'map'))
#sapply(orig_res_dist_list, function(x)make_demo_dist_map(CONFIG_FOLDER, x, 'population', map_type = 'map'))


plot_folder = paste0('result_analysis/', POTENTIAL_CONFIG_FOLDER)
if (file.exists(file.path(here(), plot_folder))){
    setwd(file.path(here(), plot_folder))    
} else{
    dir.create(file.path(here(), plot_folder))
    setwd(file.path(here(), plot_folder))
}

###graphs####

#Plot the edes for all runs in config_folder by demographic and population only
plot_poll_edes(potential_config_df_list[[1]])

#Plot which precincts are used for each number of polls
plot_precinct_persistence(potential_config_df_list[[2]])

###maps####
sapply(potential_res_dist_list, function(x)make_bg_maps(x, 'boundries'))
sapply(potential_res_dist_list, function(x)make_demo_dist_map(x, 'black', map_type = 'boundries'))
sapply(potential_res_dist_list, function(x)make_demo_dist_map(x, 'white', map_type = 'boundries'))
sapply(potential_res_dist_list, function(x)make_demo_dist_map(x, 'hispanic', map_type = 'boundries'))
sapply(potential_res_dist_list, function(x)make_demo_dist_map(x, 'asian', map_type = 'boundries'))

#sapply(orig_res_dist_list, function(x)make_bg_maps(POTENTIAL_CONFIG_FOLDER, x, 'map'))
#sapply(orig_res_dist_list, function(x)make_demo_dist_map(POTENTIAL_CONFIG_FOLDER, x, 'black', map_type = 'map'))
#sapply(orig_res_dist_list, function(x)make_demo_dist_map(POTENTIAL_CONFIG_FOLDER, x, 'white', map_type = 'map'))
#sapply(orig_res_dist_list, function(x)make_demo_dist_map(POTENTIAL_CONFIG_FOLDER, x, 'hispanic', map_type = 'map'))
#sapply(orig_res_dist_list, function(x)make_demo_dist_map(POTENTIAL_CONFIG_FOLDER, x, 'asian', map_type = 'map'))
#sapply(orig_res_dist_list, function(x)make_demo_dist_map(POTENTIAL_CONFIG_FOLDER, x, 'population', map_type = 'map'))

