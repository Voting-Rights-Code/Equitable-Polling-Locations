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

source('result analysis/graph_functions.R')


#######
#Set Constants
#######

#Basic constants for analysis
#LOCATION must be either a string or list of strings
#CONFIG_FOLDER must be a string

LOCATION = 'Chatham_County_GA'
CONFIG_FOLDER = 'Chatham_County_GA_original_configs'
LOCATION = 'Henrico_County_VA'
CONFIG_FOLDER = 'Henrico_County_VA_potential_configs'

#Run-type specific constants
IDEAL_POLL_NUMBER  = 9 #the optimal number of polls desired for this county

#######
#Location of original location results
#and other related constants
#######

original_locations = paste(LOCATION, 'original', 'configs', sep = '_')
#original_locations = 'Engage_VA_2024_configs'

#######
#Check that location and folders valid
#this also ensures that you are in the right folder to read data
#######

#Does the config folder 
check_config_folder_valid(CONFIG_FOLDER)
#Does the config folder contain files associated to the location
#check_location_valid(LOCATION, CONFIG_FOLDER)


#######
#Read in data
#Run this for each of the folders under consideration
#Recall, output of form: list(ede_df, precinct_df, residence_df, result_df)
#######
config_df_list <- read_result_data(LOCATION, CONFIG_FOLDER, 'placement')
#config_ede_df<- config_df_list[[1]]
#config_precinct_df<- config_df_list[[2]]
#config_residence_df<- config_df_list[[3]]
#config_result_df<- config_df_list[[4]]


orig_df_list <- read_result_data(LOCATION, original_locations, 'historical')
#defined as above

#######
#Plot data
#######
plot_folder = paste0('result analysis/', CONFIG_FOLDER)
if (file.exists(file.path(here(), plot_folder))){
    setwd(file.path(here(), plot_folder))    
} else{
    dir.create(file.path(here(), plot_folder))
    setwd(file.path(here(), plot_folder))
}

#Add percent population to data ede data for graph scaling for all general config folder and orig
pop_scaled_edes <- ede_with_pop(config_df_list)
pop_scaled_edes_orig <- ede_with_pop(orig_df_list)

#Plot the edes for all runs in config_folder by demographic and population only
plot_poll_edes(config_df_list[[1]])
plot_population_edes(config_df_list[[1]])

#Plot the edes for all runs in original_location and equivalent optimization runs by demographic
plot_original_optimized(config_df_list[[1]], orig_df_list[[1]])
plot_original_optimized(pop_scaled_edes, pop_scaled_edes_orig, '_scaled')

#Plot which precincts are used for each number of polls
plot_precinct_persistence(config_df_list[[2]])

#Boxplots of the average distances traveled and the y_edes at each run in folder
plot_boxplots(config_df_list[[3]])

#Histogram of the original distributions and that for the desired number of polls
plot_orig_ideal_hist(orig_df_list[[3]], config_df_list[[3]], IDEAL_POLL_NUMBER)

