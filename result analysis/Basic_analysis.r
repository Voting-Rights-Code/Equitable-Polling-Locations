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

LOCATION = 'Chatham_County_GA'
ORIG_CONFIG_FOLDER = 'Chatham_County_GA_original_configs'
POTENTIAL_CONFIG_FOLDER = 'Chatham_County_GA_no_bg_school_configs'

#Run-type specific constants
IDEAL_POLL_NUMBER  = 9 #the optimal number of polls desired for this county

#######
#Check that location and folders valid
#this also ensures that you are in the right folder to read data
#######

#Does the config folder exist?
check_config_folder_valid(ORIG_CONFIG_FOLDER)
check_config_folder_valid(POTENTIAL_CONFIG_FOLDER)

#Does the config folder contain files associated to the location
check_location_valid(LOCATION, ORIG_CONFIG_FOLDER)
check_location_valid(LOCATION, POTENTIAL_CONFIG_FOLDER)

#######
#Read in data
#Run this for each of the folders under consideration
#Recall, output of form: list(ede_df, precinct_df, residence_df, result_df)
#######
#driving flags
config_list<-c(ORIG_CONFIG_FOLDER, POTENTIAL_CONFIG_FOLDER)
DRIVING_FLAG <- set_global_driving_flag(config_list)


orig_config_df_list <- read_result_data(LOCATION, ORIG_CONFIG_FOLDER)
#config_ede_df<- config_df_list[[1]]
#config_precinct_df<- config_df_list[[2]]
#config_residence_df<- config_df_list[[3]]
#config_result_df<- config_df_list[[4]]


potential_config_df_list <- read_result_data(LOCATION, POTENTIAL_CONFIG_FOLDER)
#defined as above

#change descriptor
orig_config_df_list = lapply(orig_config_df_list, function(x){x[ , descriptor:= gsub('year_', 'Hisorical ', descriptor)]})
penalized_config_df_list = lapply(potential_config_df_list, function(x){x[ , descriptor:= gsub('precincts_open_', 'Optimized ', descriptor)]})


#########
#Set up maps and cartograms
#########
#set result folder
result_folder = paste(LOCATION, 'results', sep = '_')

#get all file names the result_folder with the strings config_folder and 'residence_distances'
res_dist_list = list.files(result_folder)[grepl('residence_distances', list.files(result_folder))]
orig_res_dist_list = res_dist_list[grepl(ORIG_CONFIG_FOLDER, res_dist_list)]
potential_res_dist_list = res_dist_list[grepl(POTENTIAL_CONFIG_FOLDER, res_dist_list)]


#get avg distance bounds for map coloring
all_color_bounds <- mapply(function(location, config_folder){distance_bounds(location, config_folder)}, LOCATION, config_list)
if (any(is.na(all_color_bounds))){
    warning('Some location does not have a min or max average distance for mapping')
}
global_min <- min(unlist(all_color_bounds))
global_max <- max(unlist(all_color_bounds))
color_bounds <- list(global_min, global_max)

#######
#Plot potential data
#######
plot_folder = paste0('result analysis/', POTENTIAL_CONFIG_FOLDER)
if (file.exists(file.path(here(), plot_folder))){
    setwd(file.path(here(), plot_folder))    
} else{
    dir.create(file.path(here(), plot_folder))
    setwd(file.path(here(), plot_folder))
}

###graphs####

#Add percent population to data ede data for graph scaling for all general config folder and orig
orig_pop_scaled_edes <- ede_with_pop(orig_config_df_list)
potential_pop_scaled_edes <- ede_with_pop(potential_config_df_list)

#Plot the edes for all runs in config_folder by demographic and population only
plot_poll_edes(potential_config_df_list[[1]])
plot_population_edes(potential_config_df_list[[1]])

#Plot the edes for all runs in original_location and equivalent optimization runs by demographic
plot_original_optimized(potential_config_df_list[[1]], orig_config_df_list[[1]])
plot_original_optimized(potential_pop_scaled_edes, orig_pop_scaled_edes, '_scaled')

#Plot which precincts are used for each number of polls
plot_precinct_persistence(potential_config_df_list[[2]])

#Boxplots of the average distances traveled and the y_edes at each run in folder
plot_boxplots(potential_config_df_list[[3]])

#Histogram of the original distributions and that for the desired number of polls
plot_orig_ideal_hist(orig_config_df_list[[3]], potential_config_df_list[[3]], IDEAL_POLL_NUMBER)

###maps####
sapply(potential_res_dist_list, function(x)make_bg_maps(x, 'map'))
sapply(potential_res_dist_list, function(x)make_demo_dist_map(x, 'population'))
sapply(potential_res_dist_list, function(x)make_demo_dist_map(x, 'black'))
sapply(potential_res_dist_list, function(x)make_demo_dist_map(x, 'white'))
sapply(potential_res_dist_list, function(x)make_demo_dist_map(x, 'hispanic'))
sapply(potential_res_dist_list, function(x)make_demo_dist_map(x, 'asian'))


#######
#Plot orig data
#######
plot_folder = paste0('result analysis/', ORIG_CONFIG_FOLDER)
if (file.exists(file.path(here(), plot_folder))){
    setwd(file.path(here(), plot_folder))    
} else{
    dir.create(file.path(here(), plot_folder))
    setwd(file.path(here(), plot_folder))
}

###maps####
sapply(orig_res_dist_list, function(x)make_bg_maps(x, 'map'))
sapply(orig_res_dist_list, function(x)make_demo_dist_map(x, 'population'))
sapply(orig_res_dist_list, function(x)make_demo_dist_map(x, 'black'))
sapply(orig_res_dist_list, function(x)make_demo_dist_map(x, 'white'))
sapply(orig_res_dist_list, function(x)make_demo_dist_map(x, 'hispanic'))
sapply(orig_res_dist_list, function(x)make_demo_dist_map(x, 'asian'))

