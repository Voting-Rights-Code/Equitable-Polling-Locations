library(here)

#######
#Change directory
#######
setwd(here())

#######
#source functions
#######

source('R/result_analysis/graph_functions.R')
source('R/result_analysis/map_functions.R')

#######
#Set Constants
#######

#Basic constants for analysis
#LOCATION must be either a string or list of strings
#CONFIG_FOLDER must be a string

LOCATION = 'Gwinnett_County_GA'
CONFIG_FOLDER = 'Gwinnett_County_GA_12_for_2024_configs'

PENALIZED_CONFIG_FOLDER = 'Gwinnett_County_GA_12_for_2024_penalized_configs'

# This is where this analysis will be stored in the cloud
STORAGE_BUCKET = 'equitable-polling-analysis-scratch'
CLOUD_STORAGE_ANALYSIS_NAME = 'Gwinnette_12_for_2024_graphs.r'

#constants for reading data
READ_FROM_CSV = FALSE

#constants for database queries
#only need to define if READ_FROM_CSV = TRUE
PROJECT = "equitable-polling-locations"
DATASET = "equitable_polling_locations_prod"
BILLING = PROJECT

#Connect to database if needed
#returns NULL if READ_FROM_CSV = TRUE
POLLING_CON <- define_connection()

#######
#Check that location and folders valid
#this also ensures that you are in the right folder to read data
#######

#Load config data
#checking if the config folder is valid
#and that the location is in the indicated dataset
config_dt <- load_config_data(LOCATION, CONFIG_FOLDER)
penalized_config_dt <- load_config_data(LOCATION, PENALIZED_CONFIG_FOLDER)

#get driving flags
config_dt_list<-c(config_dt, penalized_config_dt)
DRIVING_FLAG <- set_global_driving_flag(config_dt_list)


#######
#Read in data
#Run this for each of the folders under consideration
#Recall, output of form: list(ede_df, precinct_df, residence_df, result_df)
#######

#names of the output data in these lists
#come from TABLES above
config_output_df_list <- read_result_data(config_dt)

penalized_output_df_list <- read_result_data(penalized_config_dt, 'penalized_sites')

#change descriptor
change_descriptors <- function(df){
    df <- df[descriptor == "bad_types_bg_centroid|Elec Day School - Potential|EV_2022_cease", descriptor := "Both"
            ][descriptor == "bad_types_bg_centroid|Elec Day Church - Potential|Elec Day School - Potential|EV_2022_cease", descriptor := "Fire Stations"
            ][descriptor == "bad_types_bg_centroid|Elec Day School - Potential|EV_2022_cease|Fire Station - Potential", descriptor := "Churches"
            ][descriptor == "bad_types_bg_centroid|Elec Day Church - Potential|Elec Day School - Potential|EV_2022_cease|Fire Station - Potential", descriptor := "Neither"
            ]
return(df)
}
config_output_df_list = lapply(config_output_df_list, change_descriptors)
penalized_output_df_list <- lapply(penalized_output_df_list, function(x){x[ , descriptor := 'Penalized']})

#########
#Set up maps and cartograms
#########
#set result folder
result_folder = paste(LOCATION, 'results', sep = '_')

#get all file names the result_folder with the strings config_folder and 'residence_distances'
config_list_prepped <- prepare_outputs_for_maps(config_output_df_list$residence_distances, config_output_df_list$result, config_dt)

penalized_list_prepped <- prepare_outputs_for_maps(penalized_output_df_list$residence_distances, penalized_output_df_list$result, penalized_config_dt)

#get avg distance bounds for map coloring
all_res_output <- do.call(rbind, c(config_list_prepped, penalized_list_prepped))

global_color_bounds <- distance_bounds(all_res_output)

#######
#Plot data
#######
plot_folder = paste0('result_analysis/', CONFIG_FOLDER)
if (!file.exists(file.path(here(), plot_folder))){
    dir.create(file.path(here(), plot_folder))
}
setwd(file.path(here(), plot_folder))

###graphs####

#Add percent population to data ede data for graph scaling for all general config folder and orig
pop_scaled_edes <- ede_with_pop(config_output_df_list)
penalized_pop_scaled_edes <- ede_with_pop(penalized_output_df_list)

#Plot the edes for all runs in original_location and equivalent optimization runs by demographic
pop_scaled_list = list(pop_scaled_edes, penalized_pop_scaled_edes)
combined_pop_scaled_edes <- combine_different_runs(pop_scaled_list)
plot_historic_edes(combined_pop_scaled_edes, suffix = 'pop_scaled')

###maps####
res_dist_list = c(config_list_prepped, penalized_list_prepped)
sapply(res_dist_list, function(x)make_bg_maps(x, 'map'))
sapply(res_dist_list, function(x)make_demo_dist_map(x, 'black'))
sapply(res_dist_list, function(x)make_demo_dist_map(x, 'white'))

upload_graph_files_to_cloud_storage()
