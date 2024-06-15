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

LOCATION = 'Intersecting_Madison_City_of_WI'
CONFIG_FOLDER = 'Intersecting_Madison_City_of_WI_original_configs'

#Run-type specific constants
#IDEAL_POLL_NUMBER  = 19 #the optimal number of polls desired for this county

#######
#Location of original location results
#and other related constants
#######

#original_locations = paste(LOCATION, 'original', 'configs', sep = '_')

#######
#Check that location and folders valid
#this also ensures that you are in the right folder to read data
#######

#Does the config folder exist?
check_config_folder_valid(CONFIG_FOLDER)
#Does the config folder contain files associated to the location
check_location_valid(LOCATION, CONFIG_FOLDER)


#######
#Read in data
#Run this for each of the folders under consideration
#Recall, output of form: list(ede_df, precinct_df, residence_df, result_df)
#######
config_df_list <- read_result_data(LOCATION, CONFIG_FOLDER, 'other')
#config_ede_df<- config_df_list[[1]]
#config_precinct_df<- config_df_list[[2]]
#config_residence_df<- config_df_list[[3]]
#config_result_df<- config_df_list[[4]]

change_descriptors <- function(df){
    df <- df[descriptor == "original_all_2024", descriptor := "All locations"
            ][descriptor == "original_walkin_2024", descriptor := "Walk ins"
            ]
return(df)
}
config_df_list = lapply(config_df_list, change_descriptors)


#orig_df_list <- read_result_data(LOCATION, original_locations, 'historical')
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
#pop_scaled_edes_orig <- ede_with_pop(orig_df_list)
#pop_scaled_edes_orig <- ede_with_pop(orig_df_list)

#Plot the edes for all runs in config_folder by demographic and population only
#plot_poll_edes(config_df_list[[1]])
#plot_population_edes(config_df_list[[1]])

#Plot the edes for all runs in original_location and equivalent optimization runs by demographic
plot_historic_edes(CONFIG_FOLDER, pop_scaled_edes, suffix = 'pop_scaled')


#Histogram of the original distributions and that for the desired number of polls
#plot_orig_ideal_hist(orig_df_list[[3]], config_df_list[[3]], IDEAL_POLL_NUMBER)
#ggplot(config_df_list[[3]], aes(x = avg_dist, fill = descriptor)) + 
#		geom_histogram(aes(weight = demo_pop), position = "dodge", alpha = 0.8)+
#		labs(x = 'Average distance traveled to poll (m)', y = 'Number of people', fill = 'Optimization Run') 
#		ggsave('avg_dist_distribution_hist.png')
