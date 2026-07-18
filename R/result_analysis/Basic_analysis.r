library(here)
library(gargle)
options(gargle_oauth_email = TRUE)

#######
#Change directory:
#Sets directory to the git home directory
#######
setwd(here())

#######
#source functions
#1. storage.R contains functions for putting outputs on Google Cloud Storage
#2. graph_functions.R (contains too much) contains all the functions for 
#   reading data, checking data, processing graphs/ maps / regressions, plotting
#   graphs and computing regresssions
#3. map_functions.R contains all the functions for reading in the data and 
#   plotting the maps
#######

source('R/result_analysis/utility_functions/storage.R')
source('R/result_analysis/utility_functions/graph_functions.R')
source('R/result_analysis/utility_functions/map_functions.R')
source('R/result_analysis/utility_functions/regression_functions.R')


#######
#Read in command line arguments
#Note: 1. This is now run from command line. A config file 
#      must be given to get the constants for the analysis to be run
#      2. In the case of only doing historical analysis, and not comparing 
#      against any changes to what is historically present, the 
#      POTENTIAL_CONFIG_FOLDER must be NULL in the config file. Then all 
#      functions in this file that uses this constant and their ouputs are 
#      adjusted to ignore this input or return NULL.
#     3. Note: for now, this only works for a unique location. Extending this to the location being the varying field is still a TODO.
#     4. run 
#######

#args = commandArgs(trailingOnly = TRUE)
#if (length(args) != 1){
#     stop("Must enter exactly one config file") 
#    } else{#read constants from indicated config file
#    config_path <- paste0('R/result_analysis/Basic_analysis_configs/', args[1])
#    source(config_path)
#}

###
#For inline testing only
###
source('R/result_analysis/Basic_analysis_configs/Monongalia_County_original_driving.r')

#source('R/result_analysis/Basic_analysis_configs/Monongalia_County_original_driving_for_test.r')

#source('R/result_analysis/Basic_analysis_configs/Dougherty_County_original_and_log.r')

#######
#Check that location and folders valid
#Load configs and get driving / log flags
#######

#Load config data
#checking if the config folder is valid
#and that the location is in the indicated dataset
orig_config_dt <- load_config_data(LOCATION, ORIG_CONFIG_FOLDER)
potential_config_dt <- load_config_data(LOCATION, POTENTIAL_CONFIG_FOLDER)
config_dt_list<-c(orig_config_dt, potential_config_dt)

#get driving flags
DRIVING_FLAG <- set_global_flag(config_dt_list, 'driving')


#######
#Read in data
#Run this for each of the folders under consideration
#update description to custom descriptors if desired.
#Recall, output of form: list(ede_df, precinct_df, residence_df, results_df)
#######

#names of the output data in these lists
#come from TABLES defined in graph_functions.R

orig_output_df_list <- read_result_data(orig_config_dt, field_of_interest = ORIG_FIELD_OF_INTEREST, descriptor_dict = DESCRIPTOR_DICT_ORIG)

potential_output_df_list <- read_result_data(potential_config_dt, field_of_interest = POTENTIAL_FIELD_OF_INTEREST, 
descriptor_dict = DESCRIPTOR_DICT_POTENTIAL)

#########
#Decide, once, whether each folder -- and the orig+potential combination,
#if there is one -- has a single, consistent distance/time unit. Plots
#that need one unit for their whole y-axis are gated on these below.
#Maps and plot_density_v_distance_bg are not gated: they handle a mix of
#units correctly by splitting, and don't consume these checks.
#########

orig_flag_strs <- resolve_flag_strs(orig_output_df_list$edes, 'orig_data', DRIVING_FLAG)

potential_flag_strs <- if (!is.null(potential_output_df_list)) {
	resolve_flag_strs(potential_output_df_list$edes, 'potential_data', DRIVING_FLAG)
} else {
	NULL
}

combined_flag_strs <- if (!is.null(orig_flag_strs) && !is.null(potential_flag_strs)) {
	resolve_combined_flag_strs(
		c(unique(orig_output_df_list$edes$metric), unique(potential_output_df_list$edes$metric)),
		'orig_and_potential_combined', DRIVING_FLAG)
} else {
	NULL
}

#########
#Set up maps
#1. Aggregate data above to block group level and split by config name
#2. Calculate a single average distance bound across all datasets
#########

#for block group maps
#split results by config_name 
#Merge map and result_df at block group level
orig_list_prepped <- prepare_outputs_for_bg_maps( orig_output_df_list$result)
potential_list_prepped <- prepare_outputs_for_bg_maps( potential_output_df_list$result)

#get avg distance bounds for map coloring
#This defines a global max and min to 
#set the same scale for orig and potential
#Note: maps are colored by avg distance, not ede value
all_prepped_output <- do.call(rbind, c(orig_list_prepped, potential_list_prepped))
all_prepped_output <- all_prepped_output[demographic == 'population', ][, avg_dist := demo_avg_dist]
global_color_bounds <- distance_bounds(all_prepped_output)

#for precinct and other block level maps
#split results by config_name 
#Merge with geography at block level
orig_list_block_prepped <-prepare_outputs_for_precinct_maps(orig_output_df_list$result)
potential_list_block_prepped <-prepare_outputs_for_precinct_maps(potential_output_df_list$result)
#########
#Set up regressions
#########

#combine result data with block area data to get population density and related measures
orig_regression_data <- get_density_data(orig_output_df_list$result)
potential_regression_data <- get_density_data(potential_output_df_list$result)

#take density data and aggregate key columns up to the block group level
orig_bg_density_demo<- lapply(orig_list_prepped, function(df)bg_data(df))
potential_bg_density_demo <- lapply(potential_list_prepped, function(df)bg_data(df))

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

    #Make the graphs that require the potential data to have a unique unit

    if (!is.null(potential_flag_strs)) {
        #Plot the edes for all runs in config_folder by demographic and population only
        plot_poll_edes(potential_output_df_list$edes, potential_flag_strs)
        plot_population_edes(potential_output_df_list$edes, potential_flag_strs)

        #Boxplots of the average distances traveled and the y_edes at each run in folder
        plot_boxplots(potential_output_df_list$residence_distances, potential_flag_strs)
    }

    #Make the graphs that require the combined potential and original data to have a unique unit

    if (!is.null(combined_flag_strs)) {
        #Add percent population to data ede data for graph scaling for all general config folder and orig
        orig_pop_scaled_edes <- ede_with_pop(orig_output_df_list)
        potential_pop_scaled_edes <- ede_with_pop(potential_output_df_list)

        #Plot the edes for all runs in original_location and equivalent optimization runs by demographic
        plot_original_optimized(potential_output_df_list$edes, orig_output_df_list$edes, combined_flag_strs)
        plot_original_optimized(potential_pop_scaled_edes, orig_pop_scaled_edes, combined_flag_strs, '_scaled')
 
        #Histogram of the original distributions and that for the desired number of polls
        plot_orig_ideal_hist(orig_output_df_list$residence_distances, potential_output_df_list$residence_distances, IDEAL_POLL_NUMBER, combined_flag_strs)

        #Histograms of the original distributions by race and that for the desired number of polls
        plot_original_optimized_demographic_hists(potential_output_df_list$residence_distances, orig_output_df_list$residence_distances, DEMOGRAPHIC_LIST, combined_flag_strs)
    }

    #Make the graphs that do not require a unique unit

    #Plot which precincts are used for each number of polls
    plot_precinct_persistence(potential_output_df_list$precinct_distances)

    #plot distance v density graphs and regressions
    plot_density_v_distance_bg(rbindlist(potential_bg_density_demo), LOCATION, DEMOGRAPHIC_LIST)

    potential_bg_coefs <- bg_level_naive_regression(rbindlist(potential_bg_density_demo))


    ###maps####

    #maps don't need a unique unit
    
    sapply(potential_list_prepped, function(x)make_bg_maps(x))
    sapply(potential_list_prepped, function(x)make_demo_dist_map(x, 'population'))
    sapply(potential_list_prepped, function(x)make_demo_dist_map(x, 'black'))
    sapply(potential_list_prepped, function(x)make_demo_dist_map(x, 'white'))
    sapply(potential_list_prepped, function(x)make_demo_dist_map(x, 'hispanic'))
    sapply(potential_list_prepped, function(x)make_demo_dist_map(x, 'asian'))
    sapply(potential_list_block_prepped, function(x)make_precinct_map_no_people(x))
    sapply(potential_list_block_prepped, function(x)make_precinct_map(x))
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

#Make the graphs that require the potential data to have a unique unit

if (!is.null(orig_flag_strs)) {
    #Plot the edes for all runs in historical data (original_config)
    plot_historic_edes(orig_output_df_list$edes, orig_flag_strs)
    orig_pop_scaled_edes <- ede_with_pop(orig_output_df_list)
    plot_historic_edes(orig_pop_scaled_edes, orig_flag_strs,'_scaled')
}

#Make the graphs that do not require a unique unit

#plot distance v density graphs and regressions
plot_population_densities(orig_regression_data)

#Plot which precincts are used for each number of polls
plot_precinct_persistence(orig_output_df_list$precinct_distances)

#plot distance v density graphs and regressions
plot_density_v_distance_bg(rbindlist(orig_bg_density_demo), LOCATION, DEMOGRAPHIC_LIST)
orig_bg_coefs <- bg_level_naive_regression(rbindlist(orig_bg_density_demo))


###maps####

#maps don't need a unique unit
sapply(orig_list_prepped, function(x)make_bg_maps(x))

sapply(orig_list_prepped, function(x)make_demo_dist_map(x, 'population'))
sapply(orig_list_prepped, function(x)make_demo_dist_map(x, 'black'))
sapply(orig_list_prepped, function(x)make_demo_dist_map(x, 'white'))
sapply(orig_list_prepped, function(x)make_demo_dist_map(x, 'hispanic'))
sapply(orig_list_prepped, function(x)make_demo_dist_map(x, 'asian'))
sapply(orig_list_block_prepped, function(x)make_precinct_map_no_people(x))
sapply(orig_list_block_prepped, function(x)make_precinct_map(x))

#upload_graph_files_to_cloud_storage()