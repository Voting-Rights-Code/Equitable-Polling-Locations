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

LOCATION = c('Contained_in_Madison_City_of_WI', 'Intersecting_Madison_City_of_WI')
CONFIG_FOLDER = 'Compare_Madison_City_of_WI_original_configs'

CONTAINED_IN_CONFIG_FOLDER = 'Contained_in_Madison_City_of_WI_potential_configs'
INTERSECTING_CONFIG_FOLDER = 'Intersecting_Madison_City_of_WI_potential_configs'


#######
#Check that location and folders valid
#this also ensures that you are in the right folder to read data
#######

#Does the config folder exist?
check_config_folder_valid(CONFIG_FOLDER)
#Does the config folder contain files associated to the location
check_location_valid(LOCATION, CONFIG_FOLDER)

#Does the config folder exist?
check_config_folder_valid(CONTAINED_IN_CONFIG_FOLDER)
#Does the config folder contain files associated to the location
check_location_valid(LOCATION[1], CONTAINED_IN_CONFIG_FOLDER)

#Does the config folder exist?
check_config_folder_valid(INTERSECTING_CONFIG_FOLDER)
#Does the config folder contain files associated to the location
check_location_valid(LOCATION[2], INTERSECTING_CONFIG_FOLDER)

#######
#Read in data
#Run this for each of the folders under consideration
#Recall, output of form: list(ede_df, precinct_df, residence_df, result_df)
#######
#driving flags
config_list<-c(CONFIG_FOLDER, CONTAINED_IN_CONFIG_FOLDER, INTERSECTING_CONFIG_FOLDER)
DRIVING_FLAG <- set_global_driving_flag(config_list)


config_df_list <- read_result_data(LOCATION, CONFIG_FOLDER)
#config_ede_df<- config_df_list[[1]]
#config_precinct_df<- config_df_list[[2]]
#config_residence_df<- config_df_list[[3]]
#config_result_df<- config_df_list[[4]]

intersecting_config_df_list <- read_result_data(LOCATION[2], INTERSECTING_CONFIG_FOLDER)
contained_in_config_df_list <- read_result_data(LOCATION[1], CONTAINED_IN_CONFIG_FOLDER)

#change descriptors
change_descriptors <- function(df){
    df <- df[descriptor == "location_Contained_in_Madison_City_of_WI", descriptor := "Contained"
            ][descriptor == "location_Intersecting_Madison_City_of_WI", descriptor := "Intersecting"
            ]
return(df)
}
config_df_list = lapply(config_df_list, change_descriptors)

#change num_polls and descriptor
contained_in_config_df_list <- lapply(contained_in_config_df_list, function(x) {x[ , num_polls:= round(as.numeric(gsub('maxpctnew_', '', descriptor))*30)][ , descriptor := 'Contained']})
intersecting_config_df_list <- lapply(intersecting_config_df_list, function(x) {x[ , num_polls:= round(as.numeric(gsub('maxpctnew_', '', descriptor))*30)][ , descriptor := 'Intersecting']})

#########
#Set up maps and cartograms
#########
#set result folder
result_folder = paste(LOCATION, 'results', sep = '_')

#get all file names the result_folder with the strings config_folder and 'residence_distances'
res_dist_list = list.files(result_folder)[grepl('residence_distances', list.files(result_folder))]
orig_res_dist_list = res_dist_list[grepl(CONFIG_FOLDER, res_dist_list)]
#potential_res_dist_list = res_dist_list[grepl(POTENTIAL_CONFIG_FOLDER, res_dist_list)]

#get avg distance bounds for map coloring
color_bounds <- distance_bounds(LOCATION, CONFIG_FOLDER)
#orig_color_bounds <- distance_bounds(LOCATION, CONFIG_FOLDER)
#potential_color_bounds <- distance_bounds(LOCATION, POTENTIAL_CONFIG_FOLDER)
#global_min <- min(orig_color_bounds[[1]], potential_color_bounds[[1]])
#global_max <- max(orig_color_bounds[[2]], potential_color_bounds[[2]])
#color_bounds <- list(global_min, global_max)


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

###graphs####

#Add percent population to data ede data for graph scaling for all general config folder and orig
pop_scaled_edes <- ede_with_pop(config_df_list)
#Plot the edes for all runs in original_location and equivalent optimization runs by demographic
plot_historic_edes(pop_scaled_edes, suffix = 'pop_scaled')

edes_to_compare <- list(contained_in_config_df_list[[1]], intersecting_config_df_list[[1]])
plot_multiple_edes(edes_to_compare, 'asian')
plot_multiple_edes(edes_to_compare, 'population')
plot_multiple_edes(edes_to_compare, 'black')
plot_multiple_edes(edes_to_compare, 'white')

###maps####
make_bg_maps(orig_res_dist_list[1], 'boundries', result_folder_name = result_folder[1], this_location = LOCATION[1])
make_bg_maps(orig_res_dist_list[2], 'map', result_folder_name = result_folder[2], this_location = LOCATION[2])

make_demo_dist_map(orig_res_dist_list[1], 'population', map_type = 'boundries', result_folder_name =  result_folder[1], this_location = LOCATION[1])
make_demo_dist_map(orig_res_dist_list[2], 'population', map_type = 'map', result_folder_name = result_folder[2], this_location = LOCATION[2])


