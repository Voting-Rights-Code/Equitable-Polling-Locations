library(here)

#######
#Change directory
#######
setwd(here())

#######
#source functions
#######

source('result analysis/graph_functions.R')

######
#placement test
######
location_p = 'Cobb_GA'
config_folder_p = 'Cobb_GA_no_bg_school_configs'


original_locations = paste(location_p, 'original', 'configs', sep = '_')
#some values for graph labeling
#county = gsub('.{3}$','',location)
#county_config_ = paste0(county, '_', 'config', '_')

config_df_list_placement <- read_result_data(location_p, config_folder_p, 'placement')
unique(config_df_list_placement[[1]]$descriptor)  

orig_df_list <- read_result_data(location_p, original_locations, 'historical')
unique(orig_df_list[[1]]$descriptor)  

######
#historic test
######
location_h = 'York_SC'
config_folder_h = 'York_SC_original_configs'
reference_tag = '2022'
#county = gsub('.{3}$','',location_historic)
#county_config_ = paste0(county, '_', 'config', '_')

config_df_list_historical <- read_result_data(location_h, config_folder_h, 'historical')
unique(config_df_list_historical[[1]]$descriptor)  


