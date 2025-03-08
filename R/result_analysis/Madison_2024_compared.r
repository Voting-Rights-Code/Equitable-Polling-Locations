library(here)

#######
#Change directory
#######
setwd(here())

#######
#source functions
#######

source('R/result_analysis/graph_functions.R')
source('R/result_analysis/map_functions.R')

#######
#Set Constants
#######

#Basic constants for analysis
#LOCATION must be either a string or list of strings
#CONFIG_FOLDER must be a string

LOCATION = c('Contained_in_Madison_City_of_WI', 'Intersecting_Madison_City_of_WI') #needed only for reading from csv and writing outputs
CONFIG_FOLDER = 'Compare_Madison_City_of_WI_original_configs'

CONTAINED_IN_CONFIG_FOLDER = 'Contained_in_Madison_City_of_WI_potential_configs'
INTERSECTING_CONFIG_FOLDER = 'Intersecting_Madison_City_of_WI_potential_configs'

# This is where this analysis will be stored in the cloud
STORAGE_BUCKET = 'equitable-polling-analysis'
CLOUD_STORAGE_ANALYSIS_NAME = 'Madison_2024_compared.r'

#constants for reading data
READ_FROM_CSV = TRUE

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
#Load configs and get driving flags
#######

#Load config data
#checking if the config folder is valid
#and that the location is in the indicated dataset
orig_config_dt <- load_config_data(LOCATION, CONFIG_FOLDER)
contained_in_config_dt <- load_config_data(LOCATION[1], CONTAINED_IN_CONFIG_FOLDER)
intersecting_config_dt <- load_config_data(LOCATION[2], INTERSECTING_CONFIG_FOLDER)

#get driving flags
config_dt_list<-c(orig_config_dt, contained_in_config_dt, intersecting_config_dt)
DRIVING_FLAG <- set_global_driving_flag(config_dt_list)

#######
#Read in data
#Run this for each of the folders under consideration
#Recall, output of form: list(ede_df, precinct_df, residence_df, result_df)
#######

#names of the output data in these lists
#come from TABLES above
config_output_df_list <- read_result_data(orig_config_dt)

intersecting_output_df_list <- read_result_data(intersecting_config_dt)

contained_in_output_df_list <- read_result_data(contained_in_config_dt)

#change descriptors
change_descriptors <- function(df){
    df <- df[descriptor == "location_Contained_in_Madison_City_of_WI", descriptor := "Contained"
            ][descriptor == "location_Intersecting_Madison_City_of_WI", descriptor := "Intersecting"
            ]
return(df)
}
config_output_df_list = lapply(config_output_df_list, change_descriptors)

#change num_polls and descriptor
contained_in_output_df_list <- lapply(contained_in_output_df_list, function(x) {x[ , num_polls:= round(as.numeric(gsub('maxpctnew_', '', descriptor))*30)][ , descriptor := 'Contained']})
intersecting_output_df_list <- lapply(intersecting_output_df_list, function(x) {x[ , num_polls:= round(as.numeric(gsub('maxpctnew_', '', descriptor))*30)][ , descriptor := 'Intersecting']})

#########
#Set up maps and cartograms
#########
#set result folder
result_folder = paste(LOCATION, 'results', sep = '_')

#get all file names the result_folder with the strings config_folder and 'residence_distances'
config_list_prepped <- prepare_outputs_for_maps(config_output_df_list$residence_distances, config_output_df_list$result, orig_config_dt)

#get avg distance bounds for map coloring
all_res_output <- do.call(rbind, config_list_prepped)

global_color_bounds <- distance_bounds(all_res_output)


#######
#Plot data
#######

plot_folder = paste0('result_analysis/', CONFIG_FOLDER)
if (!file.exists(file.path(here(), plot_folder))){
    dir.create(file.path(here(), plot_folder))
}
setwd(file.path(here(), plot_folder))

###graphs####

#Add percent population to data ede data for graph scaling for all general config folder and orig
pop_scaled_edes <- ede_with_pop(config_output_df_list)
#Plot the edes for all runs in original_location and equivalent optimization runs by demographic
plot_historic_edes(pop_scaled_edes, suffix = 'pop_scaled')

edes_to_compare <- list(contained_in_output_df_list$edes, intersecting_output_df_list$edes)
plot_multiple_edes(edes_to_compare, 'asian')
plot_multiple_edes(edes_to_compare, 'population')
plot_multiple_edes(edes_to_compare, 'black')
plot_multiple_edes(edes_to_compare, 'white')

###maps####

make_bg_maps(config_list_prepped[[1]], 'boundries', result_folder_name = result_folder[1])
make_bg_maps(config_list_prepped[[2]], 'boundries', result_folder_name = result_folder[2])

make_demo_dist_map(config_list_prepped[[1]], 'population', map_type = 'boundries', result_folder_name =  result_folder[1])
make_demo_dist_map(config_list_prepped[[2]], 'population', map_type = 'boundries', result_folder_name = result_folder[2])

upload_graph_files_to_cloud_storage()
