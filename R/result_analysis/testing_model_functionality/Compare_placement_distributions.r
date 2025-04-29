########################
# Should be outdated:
# this was written as a test suite to understand the difference between the log model and the base model
# this will not run under the current reorganization of the code 
# If this is needed for any reason, at the very least, the file paths need to be updated
########################

library(here)
library(reticulate)
use_condaenv('C:/Users/ganga/anaconda3/envs/Equitable-Polls', required = TRUE)

#######
#Change directory
#######
setwd(here())

#######
#source functions
#######

source('result_analysis/storage.R')
source('result_analysis/graph_functions.R')
source('result_analysis/map_functions.R')
source_python('model_data.py')
source_python('model_results.py')

#######
#Set Constants
#######

#Basic constants for analysis
#LOCATION must be either a string or list of strings
#CONFIG_FOLDER must be a string

LOCATION = 'Berkeley_County_SC' #needed only for reading from csv and writing outputs
#list of config folders to compare.
#MUST 
# * be of the same locations
CONFIG_FOLDER_LIST = c('Berkeley_County_SC_original_configs_log', 'Berkeley_County_SC_original_configs')

#'Greenville_County_SC_original_configs_log', 'Lexington_County_SC_original_configs_log','Richland_County_SC_original_configs_log', 'York_County_SC_original_configs_log')
FIELDS_OF_INTEREST_LIST = c('', '') #must not leave empty if config set has only one element


# This is where this analysis will be stored in the cloud
STORAGE_BUCKET = 'equitable-polling-analysis'
CLOUD_STORAGE_ANALYSIS_NAME = paste0(CONFIG_FOLDER_LIST, collapse = '_AND_')

#constants for reading data
READ_FROM_CSV = FALSE
PRINT_SQL = FALSE
DRIVING_DISTANCES_FILE = paste0('datasets/driving/', LOCATION,'/', LOCATION, '_driving_distances.csv')

#constants for database queries
#only need to define if READ_FROM_CSV = TRUE
PROJECT = "equitable-polling-locations"
DATASET = "equitable_polling_locations_prod"
BILLING = PROJECT

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
config_dt_list <- lapply(CONFIG_FOLDER, function(x){load_config_data(LOCATION, x)})

#######
#Read in data
#Run this for each of the folders under consideration
#Recall, output of form: list(ede_df, precinct_df, residence_df, result_df)
#######

#names of the output data in these lists
#come from TABLES above

output_df_list <- mapply(function(config_dt, field_of_interest){read_result_data(config_dt, field_of_interest)}, config_dt_list, FIELDS_OF_INTEREST_LIST, SIMPLIFY = FALSE)
names(output_df_list) <- CONFIG_FOLDER_LIST
output_df_list <- unlist(output_df_list, recursive = FALSE)


#######
#convert all data to same distance metric
#######
DRIVING_FLAG <- set_global_flag(config_dt_list, 'driving') 

#get haversine distances for LOCATION
source_distance_location <- paste0('datasets/polling/', LOCATION, '/', LOCATION,'.csv')
haversine_dt <- fread(source_distance_location)
haversine_dt <- haversine_dt[ , id_orig:= as.character(id_orig)]
#get results; drop source and distance_m columns
results_df_list <- output_df_list[grepl('results', names(output_df_list))]
results_df_list <- lapply(results_df_list, function(x){x[ , source:= NULL][ , distance_m:= NULL]})

#define the columns needed for merge
columns_for_merge  = c('id_orig', 'id_dest', 'source', 'distance_m')
if (DRIVING_FLAG){
    driving_distances <- insert_driving_distances(haversine_dt, DRIVING_DISTANCES_FILE, log)
    driving_distances <- as.data.table(driving_distances)
    results_updated <- lapply(results_df_list, function(x){merge(x, driving_distances[ , ..columns_for_merge], by = c('id_dest', 'id_orig'))})
} else {
    results_updated <- lapply(results_df_list, function(x){merge(x, haversine_dt[ , ..columns_for_merge], by = c('id_dest', 'id_orig'))})
}

#split results by desicriptor
split_by_descriptor <- lapply(results_updated, function(x){split(x, x$descriptor)})
split_by_descriptor <- unlist(split_by_descriptor, recursive = FALSE)
#melt to make precinct_distances file and label

residence_distance_df_list <- lapply(split_by_descriptor, function(x){as.data.frame(demographic_domain_summary(x, 'id_orig'))})
residence_distance_df_list <- Map(cbind.data.frame, residence_distance_df_list, name = gsub('.results', '' , names(residence_distance_df_list)))

precinct_distance_df_list <- lapply(split_by_descriptor, function(x){as.data.frame(demographic_domain_summary(x, 'id_dest'))})
precinct_distance_df_list <- Map(cbind.data.frame, precinct_distance_df_list, name = gsub('.results', '' , names(precinct_distance_df_list)))

alpha_new_list <- lapply(split_by_descriptor, function(x){alpha_min(x)})
beta <- unique(unlist(lapply(config_dt_list, function(x)x$beta)))
ede_df_list <- mapply(function(residence, result, alpha_new){as.data.frame(demographic_summary(residence, result, beta, alpha_new))}, residence_distance_df_list, split_by_descriptor, alpha_new_list, SIMPLIFY = FALSE)
ede_df_list <- Map(cbind.data.frame, ede_df_list, name = gsub('.results', '' , names(ede_df_list)))


#######
#Test differences in haversine and driving distance
#######

#distance_compare = merge(haversine_dt, driving_distances, by = c('id_orig', 'id_dest'))
#to_select = c('id_orig', 'id_dest', 'distance_m.x', 'distance_m.y')
#bad_distance = distance_compare[distance_m.y < .9*distance_m.x, ][ , ..to_select]
#browser()

#######
#Make plots
#######

#select the descriptor you want plots for
descriptor = 'year_2018'

#histograms
res_combined <- residence_distance_df_list[grepl(descriptor, names(residence_distance_df_list))]
combine_res_df <- as.data.table(do.call(rbind, res_combined))

compare_hist <- ggplot(combine_res_df[demographic == 'population', ], aes(x = avg_dist, fill = name)) + 
    geom_histogram(aes(weight = demo_pop), position = "dodge", alpha = 0.8)

#ede plots
ede_combined <- ede_df_list[grepl(descriptor, names(ede_df_list))]
combine_ede_df <- as.data.table(do.call(rbind, ede_combined))
y_EDE = ggplot(combine_ede_df, aes(x = name, y = y_EDE,
		group = demographic, color = demographic)) + 
        geom_point(aes(x = factor(name)),size = 5, alpha = .5)
avg = ggplot(combine_ede_df, aes(x = name, y = avg_dist,
		group = demographic, color = demographic))+ 
        geom_point(aes(x = factor(name)),size = 5, alpha = .5)

prec_combined <- precinct_distance_df_list[grepl(descriptor, names(precinct_distance_df_list))]
combine_prec_df <- as.data.table(do.call(rbind, prec_combined))
distance_population <- ggplot(combine_prec_df[demographic == 'population'], aes(x = weighted_dist, y = demo_pop,
		group = name,shape = name, color = name)) + 
        geom_point(size = 5, alpha = .5)