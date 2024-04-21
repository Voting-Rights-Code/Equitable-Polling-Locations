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

location = c('Fairfax_County_VA', 'Loudon_County_VA', 'Norfolk_City_VA', 'Virginia_Beach_City_VA')
config_folder = 'Engage_VA_2024_driving_configs'


#######
#Check that config folder valid
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
config_df_list <- read_result_data(config_folder, 'historical')
#config_ede_df<- config_df_list[[1]]
#config_precinct_df<- config_df_list[[2]]
#config_residence_df<- config_df_list[[3]]
#config_result_df<- config_df_list[[4]]


#######
#Constants for mapping
#######
#set result folder
result_folder = paste(LOCATION, 'results', sep = '_')

#get all file names the result_folder with the strings config_folder and 'residence_distances'
res_dist_list = list.files(result_folder)[grepl('residence_distances', list.files(result_folder))]
res_dist_list = res_dist_list[grepl(CONFIG_FOLDER, res_dist_list)]

#get avg distance bounds for maps
color_bounds <- distance_bounds(config_folder)


#######
#Plot data
#######
plot_folder = paste0('result analysis/', config_folder)
if (file.exists(file.path(here(), plot_folder))){
    setwd(file.path(here(), plot_folder))    
} else{
    dir.create(file.path(here(), plot_folder))
    setwd(file.path(here(), plot_folder))
}


#Plot the edes for all runs in original_location and equivalent optimization runs by demographic

#join ede data with population data for scaling
pop_scaled_edes <- ede_with_pop(config_df_list)
#population scaled graph
plot_election_edes(pop_scaled_edes, suffix = 'pop_scaled')
#unscaled graph
plot_election_edes(config_df_list[[1]], suffix ='')

#########
#Make maps and cartograms
#########

#Choosing not to do cartograms because of convergence difficulties

mapply(function(x,y, z){make_bg_maps(CONFIG_FOLDER, x, 'map', result_folder_name = y, this_location = z)}, res_dist_list, result_folder, location)

#mapply(function(x,y, z){make_bg_maps(x, 'cartogram', result_folder_name = y, this_location = z)}, res_dist_list, result_folder, location)

mapply(function(x,y, z){make_demo_dist_map(CONFIG_FOLDER, x, 'white', result_folder_name = y, this_location = z)}, res_dist_list, result_folder, location)

mapply(function(x,y, z){make_demo_dist_map(CONFIG_FOLDER, x, 'black', result_folder_name = y, this_location = z)}, res_dist_list, result_folder, location)

mapply(function(x,y, z){make_demo_dist_map(CONFIG_FOLDER, x, 'population', result_folder_name = y, this_location = z)}, res_dist_list, result_folder, location)


