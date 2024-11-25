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

#constants for reading data
READ_FROM_CSV = TRUE
TABLES = c("edes", "precinct_distances", "residence_distances", "result")

#constants for database queries
#only need to define if READ_FROM_CSV = TRUE
PROJECT = "equitable-polling-locations"
DATASET = "polling"
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
potential_config_dt <- load_config_data(LOCATION, POTENTIAL_CONFIG_FOLDER)

#get driving flags
config_dt_list<-c(config_dt, potential_config_dt)
DRIVING_FLAG <- set_global_driving_flag(config_dt_list)


#######
#Read in data
#Run this for each of the folders under consideration
#Recall, output of form: list(ede_df, precinct_df, residence_df, result_df)
#######

#names of the output data in these lists
#come from TABLES above
config_output_df_list <- read_result_data(config_dt)

potential_output_df_list <- read_result_data(potential_config_dt)

#########
#Set up maps and cartograms
#########
#set result folder to read data from
result_folder = paste(LOCATION, 'results', sep = '_')

#get all file names the result_folder with the strings config_folder and 'residence_distances'
config_list_prepped <- prepare_outputs_for_maps(config_output_df_list$residence_distances, config_output_df_list$result, config_dt)

potential_list_prepped <- prepare_outputs_for_maps(potential_output_df_list$residence_distances, potential_output_df_list$result, potential_config_dt)


#######
#Plot data
#######
plot_folder = paste0('result analysis/', CONFIG_FOLDER)
if (!file.exists(file.path(here(), plot_folder))){
    dir.create(file.path(here(), plot_folder))
}
setwd(file.path(here(), plot_folder))

###graphs####

#Add percent population to data ede data for graph scaling for all general config folder and orig
pop_scaled_edes <- ede_with_pop(config_df_list)
#Plot the edes for all runs in original_location and equivalent optimization runs by demographic
plot_historic_edes(pop_scaled_edes, suffix = 'pop_scaled')

plot_precinct_persistence(config_df_list[[2]])

####maps####
sapply(config_list_prepped, function(x)make_bg_maps(x, 'boundries'))
sapply(config_list_prepped, function(x)make_demo_dist_map(x, 'black', map_type = 'boundries'))
sapply(config_list_prepped, function(x)make_demo_dist_map(x, 'white', map_type = 'boundries'))
sapply(config_list_prepped, function(x)make_demo_dist_map(x, 'hispanic', map_type = 'boundries'))
sapply(config_list_prepped, function(x)make_demo_dist_map(x, 'asian', map_type = 'boundries'))
sapply(config_list_prepped, function(x)make_demo_dist_map(x, 'population', map_type = 'boundries'))

sapply(config_list_prepped, function(x)make_bg_maps(x, 'map'))



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
sapply(potential_list_prepped, function(x)make_bg_maps(x, 'boundries'))
sapply(potential_list_prepped, function(x)make_demo_dist_map(x, 'black', map_type = 'boundries'))
sapply(potential_list_prepped, function(x)make_demo_dist_map(x, 'white', map_type = 'boundries'))
sapply(potential_list_prepped, function(x)make_demo_dist_map(x, 'hispanic', map_type = 'boundries'))
sapply(potential_list_prepped, function(x)make_demo_dist_map(x, 'asian', map_type = 'boundries'))
