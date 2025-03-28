library(here)

#######
#Change directory
#######
setwd(here())

#######
#source functions
#######

source('R/result_analysis/storage.R')
source('R/result_analysis/graph_functions.R')
source('R/result_analysis/map_functions.R')

#######
#Set Constants
#######

#Basic constants for analysis
#LOCATION must be either a string or list of strings
#CONFIG_FOLDER must be a string

LOCATION = 'DeKalb_County_GA' #needed only for reading from csv and writing outputs
ORIG_CONFIG_FOLDER = "DeKalb_County_GA_original_configs_driving_beta-2"
POTENTIAL_CONFIG_FOLDER = "DeKalb_County_GA_no_school_penalize_bg_configs_driving_pre_EV_2024"
ORIG_FIELD_OF_INTEREST = '' #must not leave empty if config set has only one element
POTENTIAL_FIELD_OF_INTEREST = '' #must not leave empty if config set has only one element

# This is where this analysis will be stored in the cloud
STORAGE_BUCKET = 'equitable-polling-analysis'
CLOUD_STORAGE_ANALYSIS_NAME = paste0(ORIG_CONFIG_FOLDER, '_AND_', POTENTIAL_CONFIG_FOLDER)

#constants for reading data
READ_FROM_CSV = FALSE
PRINT_SQL = FALSE

#constants for database queries
#only need to define if READ_FROM_CSV = TRUE
PROJECT = "equitable-polling-locations"
DATASET = "equitable_polling_locations_prod"
BILLING = PROJECT

#Run-type specific constants
IDEAL_POLL_NUMBER  = 15 #the optimal number of polls desired for this county

#Connect to database if needed
#returns NULL if READ_FROM_CSV = TRUE
POLLING_CON <- define_connection()

#######
#refresh google cloud connection
#######
if (!READ_FROM_CSV){
    system("gcloud auth application-default login")
}
#######
#Check that location and folders valid
#Load configs and get driving flags
#######

#Load config data
#checking if the config folder is valid
#and that the location is in the indicated dataset
orig_config_dt <- load_config_data(LOCATION, ORIG_CONFIG_FOLDER)
potential_config_dt <- load_config_data(LOCATION, POTENTIAL_CONFIG_FOLDER)

#get driving flags
config_dt_list<-c(orig_config_dt, potential_config_dt)
DRIVING_FLAG <- set_global_flag(config_dt_list, 'driving') 
LOG_FLAG <- set_global_flag(config_dt_list, 'log_distance') 


#######
#Read in data
#Run this for each of the folders under consideration
#Recall, output of form: list(ede_df, precinct_df, residence_df, results_df)
#######

#names of the output data in these lists
#come from TABLES above

orig_output_df_list <- read_result_data(orig_config_dt, ORIG_FIELD_OF_INTEREST)

potential_output_df_list <- read_result_data(potential_config_dt, POTENTIAL_FIELD_OF_INTEREST)

#change descriptor
#function to set certain descriptors as desired
#change_descriptors <- function(df){
#    df <- df[descriptor == "location_Contained_in_Madison_City_of_WI", descriptor := "Contained"
#            ][descriptor == "location_Intersecting_Madison_City_of_WI", descriptor := "Intersecting"
#            ]
#return(df)
#}
#config_df_list = lapply(config_df_list, change_descriptors)

#########
#Set up maps
#########
#set result folder
result_folder = paste(LOCATION, 'results', sep = '_')


#add location to residence data, aggregate to block level, merge with polling locations and split
orig_list_prepped <- prepare_outputs_for_maps(orig_output_df_list$residence_distances, orig_output_df_list$result, orig_config_dt)
potential_list_prepped <- prepare_outputs_for_maps(potential_output_df_list$residence_distances, potential_output_df_list$result, potential_config_dt)

#get avg distance bounds for map coloring
#same scale for orig and potential
all_res_output <- do.call(rbind, c(orig_list_prepped, potential_list_prepped))
global_color_bounds <- distance_bounds(all_res_output)

#######
#Plot potential data
#######
plot_folder = paste0('result_analysis_outputs/', POTENTIAL_CONFIG_FOLDER)
if (!file.exists(file.path(here(), plot_folder))){
    dir.create(file.path(here(), plot_folder))
}
setwd(file.path(here(), plot_folder))

###graphs####

#Add percent population to data ede data for graph scaling for all general config folder and orig
orig_pop_scaled_edes <- ede_with_pop(orig_output_df_list)
potential_pop_scaled_edes <- ede_with_pop(potential_output_df_list)

#Plot the edes for all runs in config_folder by demographic and population only
plot_poll_edes(potential_output_df_list$edes)
plot_population_edes(potential_output_df_list$edes)

#Plot the edes for all runs in original_location and equivalent optimization runs by demographic
plot_original_optimized(potential_output_df_list$edes, orig_output_df_list$edes)
plot_original_optimized(potential_pop_scaled_edes, orig_pop_scaled_edes, '_scaled')

#Plot which precincts are used for each number of polls
plot_precinct_persistence(potential_output_df_list$precinct_distances)

#Boxplots of the average distances traveled and the y_edes at each run in folder
plot_boxplots(potential_output_df_list$residence_distances)

#Histogram of the original distributions and that for the desired number of polls
plot_orig_ideal_hist(orig_output_df_list$residence_distances, potential_output_df_list$residence_distances, IDEAL_POLL_NUMBER)

###maps####

sapply(potential_list_prepped, function(x)make_bg_maps(x, 'map'))
sapply(potential_list_prepped, function(x)make_demo_dist_map(x, 'population'))
sapply(potential_list_prepped, function(x)make_demo_dist_map(x, 'black'))
sapply(potential_list_prepped, function(x)make_demo_dist_map(x, 'white'))
sapply(potential_list_prepped, function(x)make_demo_dist_map(x, 'hispanic'))
sapply(potential_list_prepped, function(x)make_demo_dist_map(x, 'asian'))


#######
#Plot orig data
#######
plot_folder = paste0('result_analysis_outputs/', ORIG_CONFIG_FOLDER)
if (file.exists(file.path(here(), plot_folder))){
    setwd(file.path(here(), plot_folder))
} else{
    dir.create(file.path(here(), plot_folder))
    setwd(file.path(here(), plot_folder))
}

###maps####
density_data <- get_regression_data(LOCATION, orig_output_df_list$results)
plot_population_densities(density_data)

sapply(orig_list_prepped, function(x)make_bg_maps(x, 'map'))

sapply(orig_list_prepped, function(x)make_demo_dist_map(x, 'population'))
sapply(orig_list_prepped, function(x)make_demo_dist_map(x, 'black'))
sapply(orig_list_prepped, function(x)make_demo_dist_map(x, 'white'))
sapply(orig_list_prepped, function(x)make_demo_dist_map(x, 'hispanic'))
sapply(orig_list_prepped, function(x)make_demo_dist_map(x, 'asian'))

upload_graph_files_to_cloud_storage()