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

args = commandArgs(trailingOnly = TRUE)
if (length(args) != 1){
    stop("Must enter at least one config file")
} else{
    config_path <- paste0('R/result_analysis/Basic_analysis_configs/', args[1])
    source(config_path)
}

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
config_dt_list<-c(orig_config_dt, potential_config_dt)

#get driving flags
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

#add location to residence data, aggregate to block level, merge with polling locations and split
orig_list_prepped <- prepare_outputs_for_maps(orig_output_df_list$residence_distances, orig_output_df_list$result, orig_config_dt)
potential_list_prepped <- prepare_outputs_for_maps(potential_output_df_list$residence_distances, potential_output_df_list$result, potential_config_dt)

#get avg distance bounds for map coloring
#same scale for orig and potential
all_res_output <- do.call(rbind, c(orig_list_prepped, potential_list_prepped))
global_color_bounds <- distance_bounds(all_res_output)


#########
#Set up regressions
#########

#prepare datasets for regressions of distance versus density
orig_regression_data <- get_regression_data(LOCATION, orig_output_df_list$results)
potential_regression_data <- get_regression_data(LOCATION, potential_output_df_list$results)

orig_bg_density_demo <- bg_data(orig_regression_data)
potential_bg_density_demo <- bg_data(potential_regression_data)


if(!HISTORICAL_FLAG){
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

    #plot distance v density graphs and regressions
    plot_density_v_distance_bg(potential_bg_density_demo, LOCATION, DEMOGRAPHIC_LIST)

    potential_bg_coefs <- bg_level_naive_regression(potential_bg_density_demo)


    ###maps####

    sapply(potential_list_prepped, function(x)make_bg_maps(x, 'map'))
    sapply(potential_list_prepped, function(x)make_demo_dist_map(x, 'population'))
    sapply(potential_list_prepped, function(x)make_demo_dist_map(x, 'black'))
    sapply(potential_list_prepped, function(x)make_demo_dist_map(x, 'white'))
    sapply(potential_list_prepped, function(x)make_demo_dist_map(x, 'hispanic'))
    sapply(potential_list_prepped, function(x)make_demo_dist_map(x, 'asian'))
}

#######
#Plot orig data
#######
plot_folder = paste0('result_analysis_outputs/', ORIG_CONFIG_FOLDER)
if (file.exists(file.path(here(), plot_folder))){
    setwd(file.path(here(), plot_folder))
} else{
    dir.create(file.path(here(), plot_folder))
}
setwd(file.path(here(), plot_folder))

###historic edes####

#Plot the edes for all runs in historical data (original_config)
plot_historic_edes(orig_output_df_list$edes)
orig_pop_scaled_edes <- ede_with_pop(orig_output_df_list)
plot_historic_edes(orig_pop_scaled_edes, '_scaled')

###maps####
plot_population_densities(orig_regression_data)

sapply(orig_list_prepped, function(x)make_bg_maps(x, 'map'))

sapply(orig_list_prepped, function(x)make_demo_dist_map(x, 'population'))
sapply(orig_list_prepped, function(x)make_demo_dist_map(x, 'black'))
sapply(orig_list_prepped, function(x)make_demo_dist_map(x, 'white'))
sapply(orig_list_prepped, function(x)make_demo_dist_map(x, 'hispanic'))
sapply(orig_list_prepped, function(x)make_demo_dist_map(x, 'asian'))

#plot distance v density graphs and regressions

plot_density_v_distance_bg(orig_bg_density_demo, LOCATION, DEMOGRAPHIC_LIST)

orig_bg_coefs <- bg_level_naive_regression(orig_bg_density_demo)

upload_graph_files_to_cloud_storage()