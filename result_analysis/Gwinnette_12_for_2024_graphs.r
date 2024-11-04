#######
#Note for pull reviewer: I (SA) believe that this file is now deprecated. If #you agree, please delete this file before approving the pull request
#######
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

LOCATION = 'Gwinnett_County_GA'
CONFIG_FOLDER = 'Gwinnett_County_GA_12_for_2024_configs'

PENALIZED_CONFIG_FOLDER = 'Gwinnett_County_GA_12_for_2024_penalized_configs'


#######
#Check that location and folders valid
#this also ensures that you are in the right folder to read data
#######

#Does the config folder exist?
check_config_folder_valid(CONFIG_FOLDER)
check_config_folder_valid(PENALIZED_CONFIG_FOLDER)

#Does the config folder contain files associated to the location
check_location_valid(LOCATION, CONFIG_FOLDER)
check_location_valid(LOCATION, PENALIZED_CONFIG_FOLDER)


#######
#Read in data
#Run this for each of the folders under consideration
#Recall, output of form: list(ede_df, precinct_df, residence_df, result_df)
#######
#driving flag
config_list <- c(CONFIG_FOLDER, PENALIZED_CONFIG_FOLDER)
DRIVING_FLAG <- set_global_driving_flag(config_list)

config_df_list <- read_result_data(LOCATION, CONFIG_FOLDER)
#config_ede_df<- config_df_list[[1]]
#config_precinct_df<- config_df_list[[2]]
#config_residence_df<- config_df_list[[3]]
#config_result_df<- config_df_list[[4]]

penalized_config_df_list <- read_result_data(LOCATION, PENALIZED_CONFIG_FOLDER, field_of_interest = 'penalized_sites')

#change descriptor
change_descriptors <- function(df){
    df <- df[descriptor == "bad_types_bg_centroid|Elec Day School - Potential|EV_2022_cease", descriptor := "Both"
            ][descriptor == "bad_types_bg_centroid|Elec Day Church - Potential|Elec Day School - Potential|EV_2022_cease", descriptor := "Fire Stations"
            ][descriptor == "bad_types_bg_centroid|Elec Day School - Potential|EV_2022_cease|Fire Station - Potential", descriptor := "Churches"
            ][descriptor == "bad_types_bg_centroid|Elec Day Church - Potential|Elec Day School - Potential|EV_2022_cease|Fire Station - Potential", descriptor := "Neither"
            ]
return(df)
}
config_df_list = lapply(config_df_list, change_descriptors)
penalized_config_df_list <- lapply(penalized_config_df_list, function(x){x[ , descriptor := 'Penalized']})

#########
#Set up maps and cartograms
#########
#set result folder
result_folder = paste(LOCATION, 'results', sep = '_')

#get all file names the result_folder with the strings config_folder and 'residence_distances'
res_dist_list = list.files(result_folder)[grepl('residence_distances', list.files(result_folder))]
res_dist_list = res_dist_list[grepl(CONFIG_FOLDER, res_dist_list)|grepl(PENALIZED_CONFIG_FOLDER, res_dist_list)]

#get avg distance bounds for map coloring
base_color_bounds <- distance_bounds(LOCATION, CONFIG_FOLDER)
penalized_color_bounds <- distance_bounds(LOCATION, PENALIZED_CONFIG_FOLDER, field_of_interest = 'penalized_sites')
global_min <- min(base_color_bounds[[1]], penalized_color_bounds[[1]])
global_max <- max(base_color_bounds[[2]], penalized_color_bounds[[2]])
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

#Add percent population to data ede data for graph scaling for all general config folder and orig
pop_scaled_edes <- ede_with_pop(config_df_list)
penalized_pop_scaled_edes <- ede_with_pop(penalized_config_df_list)

#Plot the edes for all runs in original_location and equivalent optimization runs by demographic
pop_scaled_list = list(pop_scaled_edes, penalized_pop_scaled_edes)
combined_pop_scaled_edes <- combine_different_runs(pop_scaled_list)
plot_historic_edes(combined_pop_scaled_edes, suffix = 'pop_scaled')

###maps####
sapply(res_dist_list, function(x)make_bg_maps(x, 'map'))
sapply(res_dist_list, function(x)make_demo_dist_map(x, 'black'))
sapply(res_dist_list, function(x)make_demo_dist_map(x, 'white'))

