library(here)

#######
#Change directory
#######
setwd(here())

#######
#source functions
#######

source('R/result_analysis/graph_functions.R')


#######
#Set Constants
#######

#Basic constants for analysis
#LOCATION must be either a string or list of strings
#CONFIG_FOLDER must be a string

LOCATION = 'DeKalb_County_GA'
CONFIG_FOLDER = 'DeKalb_GA_no_school_penalize_bg_configs_driving_pre_EV_2024'

#Run-type specific constants
IDEAL_POLL_NUMBER  = 19 #the optimal number of polls desired for this county

#######
#Location of original location results
#and other related constants
#######

original_locations = paste(LOCATION, 'original', 'configs', 'driving', sep = '_')

#######
#Check that location and folders valid
#this also ensures that you are in the right folder to read data
#######

#Does the config folder exist?
check_config_folder_valid(CONFIG_FOLDER)
check_config_folder_valid(original_locations)

#Does the config folder contain files associated to the location
check_location_valid(LOCATION, CONFIG_FOLDER)
check_location_valid(LOCATION, original_locations)


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


orig_df_list <- read_result_data(LOCATION, original_locations, 'other')
#defined as above

#change descriptors
lapply(orig_df_list, function(x){x[descriptor == 'optimal_allnew_2022', descriptor := 'All New'][descriptor == 'optimal_keep7_2022', descriptor := 'Keep 7'][descriptor == 'original_2020', descriptor := '2020'][descriptor == 'original_2022', descriptor := '2022'][descriptor == 'original_2024', descriptor := '2024']})
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

