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

LOCATION = c('Contained_in_Savannah_City_of_GA', 'Intersecting_Savannah_City_of_GA') #needed only for reading from csv and writing outputs
CONTAINED_IN_ORIG_CONFIG_FOLDER = 'Contained_in_Savannah_City_of_GA_original_configs'
INTERSECTING_ORIG_CONFIG_FOLDER = 'Intersecting_Savannah_City_of_GA_original_configs'

CONTAINED_IN_POT_CONFIG_FOLDER = 'Contained_in_Savannah_City_of_GA_no_bg_school_configs'
INTERSECTING_POT_CONFIG_FOLDER = 'Intersecting_Savannah_City_of_GA_no_bg_school_configs'

COMPARISON_FOLDER = 'Compare_Savannah_City_of_GA_configs' #only for putting files away

# This is where this analysis will be stored in the cloud
STORAGE_BUCKET = 'equitable-polling-analysis'
CLOUD_STORAGE_ANALYSIS_NAME = 'Savannah_2020_2022_compared.r'

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

contained_in_orig_config_dt <- load_config_data(LOCATION[1], CONTAINED_IN_ORIG_CONFIG_FOLDER)
intersecting_orig_config_dt <- load_config_data(LOCATION[2], INTERSECTING_ORIG_CONFIG_FOLDER)

contained_in_pot_config_dt <- load_config_data(LOCATION[1], CONTAINED_IN_POT_CONFIG_FOLDER)
intersecting_pot_config_dt <- load_config_data(LOCATION[2], INTERSECTING_POT_CONFIG_FOLDER)

#get driving flags
config_dt_list<-c(contained_in_orig_config_dt, intersecting_orig_config_dt, contained_in_pot_config_dt, intersecting_pot_config_dt)
DRIVING_FLAG <- set_global_driving_flag(config_dt_list)

#######
#Read in data
#Run this for each of the folders under consideration
#Recall, output of form: list(ede_df, precinct_df, residence_df, result_df)
#######

#names of the output data in these lists
#come from TABLES above
contained_in_orig_output_df_list <- read_result_data(contained_in_orig_config_dt)
intersecting_orig_output_df_list <- read_result_data(intersecting_orig_config_dt)

contained_in_pot_output_df_list <- read_result_data(contained_in_pot_config_dt)
intersecting_pot_output_df_list <- read_result_data(intersecting_pot_config_dt)

#change descriptor
contained_in_orig_output_df_list = lapply(contained_in_orig_output_df_list, function(x){x[, descriptor:= str_replace(descriptor, 'year', 'Contained')]})
intersecting_orig_output_df_list = lapply(intersecting_orig_output_df_list, function(x){x[, descriptor:= str_replace(descriptor, 'year', 'Intersecting')]})

contained_in_pot_output_df_list <- lapply(contained_in_pot_output_df_list, function(x) {x[ , descriptor := 'Contained']})
intersecting_pot_output_df_list <- lapply(intersecting_pot_output_df_list, function(x) {x[ , descriptor := 'Intersecting']})

#########
#Set up maps and cartograms
#########
#set result folder
result_folder = paste(LOCATION, 'results', sep = '_')

#get all file names the result_folder with the strings config_folder and 'residence_distances'
contained_in_orig_list_prepped <- prepare_outputs_for_maps(contained_in_orig_output_df_list$residence_distances, contained_in_orig_output_df_list$result, contained_in_orig_config_dt)

intersecting_orig_list_prepped <- prepare_outputs_for_maps(intersecting_orig_output_df_list$residence_distances, intersecting_orig_output_df_list$result, intersecting_orig_config_dt)


#get avg distance bounds for map coloring
all_res_output <- do.call(rbind, c(contained_in_orig_list_prepped, intersecting_orig_list_prepped))

global_color_bounds <- distance_bounds(all_res_output)

#######
#Plot data
#######

plot_folder = paste0('result_analysis/', COMPARISON_FOLDER)
if (!file.exists(file.path(here(), plot_folder))){
    dir.create(file.path(here(), plot_folder))
}
setwd(file.path(here(), plot_folder))

###graphs####

#Add percent population to data ede data for graph scaling for all general config folder and orig
contained_in_pop_scaled_edes <- ede_with_pop(contained_in_orig_output_df_list)
intersecting_pop_scaled_edes <- ede_with_pop(intersecting_orig_output_df_list)

#Plot the edes for all runs in original_location and equivalent optimization runs by demographic
pop_scaled_list = list(contained_in_pop_scaled_edes, intersecting_pop_scaled_edes)
combined_pop_scaled_edes <- combine_different_runs(pop_scaled_list)
plot_historic_edes(combined_pop_scaled_edes, suffix = 'pop_scaled')

edes_to_compare <- list(contained_in_pot_output_df_list$edes, intersecting_pot_output_df_list$edes)
plot_multiple_edes(edes_to_compare, 'asian')
plot_multiple_edes(edes_to_compare, 'population')
plot_multiple_edes(edes_to_compare, 'black')
plot_multiple_edes(edes_to_compare, 'white')

###maps####
sapply(contained_in_orig_list_prepped, function(x){make_bg_maps(x, 'boundries', result_folder_name = result_folder[1])})
sapply(intersecting_orig_list_prepped, function(x){make_bg_maps(x, 'boundries', result_folder_name = result_folder[2])})

sapply(contained_in_orig_list_prepped, function(x){make_demo_dist_map(x, 'population', map_type = 'boundries', result_folder_name =  result_folder[1])})
sapply(intersecting_orig_list_prepped, function(x){make_demo_dist_map(x, 'population', map_type = 'boundries', result_folder_name =  result_folder[2])})

upload_graph_files_to_cloud_storage()
