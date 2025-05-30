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
#######

# args = commandArgs(trailingOnly = TRUE)
# if (length(args) != 1){
#     stop("Must enter exactly one config file")
# } else{#read constants from indicated config file
#     config_path <- paste0('R/result_analysis/Basic_analysis_configs/', args[1])
#     source(config_path)
#  }

###
#For inline testing only
###
#source('R/result_analysis/Basic_analysis_configs/Berkeley_County_original.r')
source('R/result_analysis/Basic_analysis_configs/York_County_original.r')

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
LOG_FLAG <- set_global_flag(config_dt_list, 'log_distance')


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
#Set up maps
#1. Aggregate data above to block group level and split by config name
#2. Calculate a single average distance bound across all datasets
#########

#split results by config_name 
#Merge map and result_df at block group level
orig_list_prepped <- prepare_outputs_for_maps( orig_output_df_list$result)
potential_list_prepped <- prepare_outputs_for_maps( potential_output_df_list$result)

#get avg distance bounds for map coloring
#This defines a global max and min to 
#set the same scale for orig and potential
#Note: maps are colored by avg distance, not ede value
all_prepped_output <- do.call(rbind, c(orig_list_prepped, potential_list_prepped))
all_prepped_output <- all_prepped_output[demographic == 'population', ][, avg_dist := demo_avg_dist]
global_color_bounds <- distance_bounds(all_prepped_output)


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

#split by descriptor
result_list <- split(orig_output_df_list$results, orig_output_df_list$results$descriptor)
#result_list <- split(potential_output_df_list$results, potential_output_df_list$results$descriptor)



#merge in geometry data
sample <- result_list$year_2014
#sample <- result_list$precincts_open_5
location <- unique(sample$location) 
block_result_geom <- results_with_area_geom(location, sample)

#Make sf
library(dplyr)
library(sf)

df_sf <- st_as_sf(block_result_geom)

step_1 <- ggplot() +	geom_sf(data = df_sf, aes(fill = id_dest), show.legend = FALSE)+
        #coord_sf(lims_method = "geometry_bbox", default_crs = sf::st_crs(4326)) + 
        geom_point(data = df_sf, aes(x = dest_lon, y = dest_lat), show.legend = FALSE)
ggsave('step_1_all_blocks.png', step_1)

#separate out populated and unpopulated blocks
df_sf_pop <- df_sf[!is.na(df_sf$id_dest), ]
df_sf_unpop <- df_sf[is.na(df_sf$id_dest), ]

#Group by assigned dest.
#This will leave blocks with no people in a group
#precincts_sf <- df_sf %>% group_by(id_dest, descriptor, dest_lat, dest_lon) %>% summarize(precinct_geom = st_union(geometry))

precincts_sf_pop <- df_sf_pop %>% group_by(id_dest, descriptor, dest_lat, dest_lon) %>% summarize(precinct_geom = st_union(geometry))

step_2 <- ggplot() +	geom_sf(data = precincts_sf_pop, aes(fill = id_dest), show.legend = FALSE)+
        #coord_sf(lims_method = "geometry_bbox", default_crs = sf::st_crs(4326)) + 
        geom_point(data = precincts_sf_pop, aes(x = dest_lon, y = dest_lat), show.legend = FALSE)
ggsave('step_2_pop_precincts.png', step_2)

#adjust unpop data to match pop data
names(df_sf_unpop)[names(df_sf_unpop) == 'geometry'] <- 'precinct_geom'
st_geometry(df_sf_unpop) <- 'precinct_geom'
df_sf_unpop <- df_sf_unpop[, names(precincts_sf_pop)]


#associate the unpopulated / unassigned ccs to the closests assigned feature
unpop_join <- st_join(df_sf_unpop, precincts_sf_pop, join=st_nearest_feature)
unpop_narrow <- unpop_join[ , !(grepl('\\.x', names(unpop_join)))]
names(unpop_narrow) <- gsub('\\.y', '',names(unpop_narrow))

step_3 <- ggplot() +	geom_sf(data = unpop_narrow, aes(fill = id_dest), show.legend = FALSE)+
        #coord_sf(lims_method = "geometry_bbox", default_crs = sf::st_crs(4326)) + 
        geom_point(data = unpop_narrow, aes(x = dest_lon, y = dest_lat), show.legend = FALSE)
ggsave('step_3_assign_unpop_precincts.png', step_3)

#combine populated and unpopulated data
precincts_sf_all <- rbind(unpop_narrow, precincts_sf_pop) %>% group_by(id_dest, descriptor, dest_lat, dest_lon) %>% summarize(precinct_geom = st_union(precinct_geom))

step_4<- ggplot() +	geom_sf(data = precincts_sf_all, aes(fill = id_dest), show.legend = FALSE)+
        #coord_sf(lims_method = "geometry_bbox", default_crs = sf::st_crs(4326)) + 
        geom_point(data = precincts_sf_all, aes(x = dest_lon, y = dest_lat), show.legend = FALSE)
ggsave('step_4_all_precincts.png', step_4)