library(here)

#######
#Change directory
#######
setwd(here())

#######
#source functions
#######

source('result analysis/graph_functions.R')
source('result analysis/map_functions.R')

#######
#Set Constants
#######

#Basic constants for analysis
#LOCATION must be either a string or list of strings
#CONFIG_FOLDER must be a string

LOCATION = c('Contained_in_Savannah_City_of_GA', 'Intersecting_Savannah_City_of_GA')
CONTAINED_IN_ORIG_CONFIG_FOLDER = 'Contained_in_Savannah_City_of_GA_original_configs'
INTERSECTING_ORIG_CONFIG_FOLDER = 'Intersecting_Savannah_City_of_GA_original_configs'

CONTAINED_IN_POT_CONFIG_FOLDER = 'Contained_in_Savannah_City_of_GA_no_bg_school_configs'
INTERSECTING_POT_CONFIG_FOLDER = 'Intersecting_Savannah_City_of_GA_no_bg_school_configs'

COMPARISON_FOLDER = 'Compare_Savannah_City_of_GA_configs'
#######
#Check that location and folders valid
#this also ensures that you are in the right folder to read data
#######

#Do the config folders exist?
check_config_folder_valid(CONTAINED_IN_ORIG_CONFIG_FOLDER)
check_config_folder_valid(INTERSECTING_ORIG_CONFIG_FOLDER)
check_config_folder_valid(CONTAINED_IN_POT_CONFIG_FOLDER)
check_config_folder_valid(INTERSECTING_POT_CONFIG_FOLDER)


#Does the config folder contain files associated to the location
check_location_valid(LOCATION[1], CONTAINED_IN_ORIG_CONFIG_FOLDER)
check_location_valid(LOCATION[2], INTERSECTING_ORIG_CONFIG_FOLDER)
check_location_valid(LOCATION[1], CONTAINED_IN_POT_CONFIG_FOLDER)
check_location_valid(LOCATION[2], INTERSECTING_POT_CONFIG_FOLDER)

#######
#Read in data
#Run this for each of the folders under consideration
#Recall, output of form: list(ede_df, precinct_df, residence_df, result_df)
#######
#driving flags
config_list<-c(CONTAINED_IN_ORIG_CONFIG_FOLDER, INTERSECTING_ORIG_CONFIG_FOLDER,    CONTAINED_IN_POT_CONFIG_FOLDER, INTERSECTING_POT_CONFIG_FOLDER)
DRIVING_FLAG <- set_global_driving_flag(config_list)


contained_in_orig_df_list <- read_result_data(LOCATION[1], CONTAINED_IN_ORIG_CONFIG_FOLDER)
intersecting_orig_df_list <- read_result_data(LOCATION[2], INTERSECTING_ORIG_CONFIG_FOLDER)

contained_in_pot_df_list <- read_result_data(LOCATION[1], CONTAINED_IN_POT_CONFIG_FOLDER)
intersecting_pot_df_list <- read_result_data(LOCATION[2], INTERSECTING_POT_CONFIG_FOLDER)

#change descriptor
contained_in_orig_df_list = lapply(contained_in_orig_df_list, function(x){x[, descriptor:= str_replace(descriptor, 'year', 'Contained')]})
intersecting_orig_df_list = lapply(intersecting_orig_df_list, function(x){x[, descriptor:= str_replace(descriptor, 'year', 'Intersecting')]})

contained_in_pot_df_list <- lapply(contained_in_pot_config_df_list, function(x) {x[ , descriptor := 'Contained']})
intersecting_pot_df_list <- lapply(intersecting_pot_config_df_list, function(x) {x[ , descriptor := 'Intersecting']})

#########
#Set up maps and cartograms
#########
#set result folder
result_folder = paste(LOCATION, 'results', sep = '_')

#get all file names the result_folder with the strings config_folder and 'residence_distances'
res_dist_list = list.files(result_folder)[grepl('residence_distances', list.files(result_folder))]
orig_res_dist_list = res_dist_list[grepl(CONTAINED_IN_ORIG_CONFIG_FOLDER, res_dist_list)|grepl(INTERSECTING_ORIG_CONFIG_FOLDER, res_dist_list)]

#get avg distance bounds for map coloring
contained_color_bounds <- distance_bounds(LOCATION[1], CONTAINED_IN_ORIG_CONFIG_FOLDER)
intersecting_color_bounds <- distance_bounds(LOCATION[2], INTERSECTING_ORIG_CONFIG_FOLDER)
global_min <- min(contained_color_bounds[[1]], intersecting_color_bounds[[1]])
global_max <- max(contained_color_bounds[[2]], intersecting_color_bounds[[2]])
color_bounds <- list(global_min, global_max)


#######
#Plot data
#######

plot_folder = paste0('result analysis/', COMPARISON_FOLDER)
if (file.exists(file.path(here(), plot_folder))){
    setwd(file.path(here(), plot_folder))
} else{
    dir.create(file.path(here(), plot_folder))
    setwd(file.path(here(), plot_folder))
}

###graphs####

#Add percent population to data ede data for graph scaling for all general config folder and orig
contained_in_pop_scaled_edes <- ede_with_pop(contained_in_orig_df_list)
intersecting_pop_scaled_edes <- ede_with_pop(intersecting_orig_df_list)

#Plot the edes for all runs in original_location and equivalent optimization runs by demographic
pop_scaled_list = list(contained_in_pop_scaled_edes, intersecting_pop_scaled_edes)
combined_pop_scaled_edes <- combine_different_runs(pop_scaled_list)
plot_historic_edes(combined_pop_scaled_edes, suffix = 'pop_scaled')

edes_to_compare <- list(contained_in_pot_df_list[[1]], intersecting_pot_df_list[[1]])
plot_multiple_edes(edes_to_compare, 'asian')
plot_multiple_edes(edes_to_compare, 'population')
plot_multiple_edes(edes_to_compare, 'black')
plot_multiple_edes(edes_to_compare, 'white')

###maps####
make_bg_maps(orig_res_dist_list[1], 'boundries', result_folder_name = result_folder[1], this_location = LOCATION[1])
make_bg_maps(orig_res_dist_list[2], 'boundries', result_folder_name = result_folder[1], this_location = LOCATION[1])
make_bg_maps(orig_res_dist_list[3], 'map', result_folder_name = result_folder[2], this_location = LOCATION[2])
make_bg_maps(orig_res_dist_list[4], 'map', result_folder_name = result_folder[2], this_location = LOCATION[2])

make_demo_dist_map(orig_res_dist_list[1], 'population', map_type = 'boundries', result_folder_name =  result_folder[1], this_location = LOCATION[1])
make_demo_dist_map(orig_res_dist_list[2], 'population', map_type = 'boundries', result_folder_name = result_folder[1], this_location = LOCATION[1])
make_demo_dist_map(orig_res_dist_list[3], 'population', map_type = 'map', result_folder_name =  result_folder[2], this_location = LOCATION[2])
make_demo_dist_map(orig_res_dist_list[4], 'population', map_type = 'map', result_folder_name =  result_folder[2], this_location = LOCATION[2])


