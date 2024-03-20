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
#Location must be part of config folder string

location = c('Fairfax_County_VA', 'Loudon_County_VA', 'Norfolk_City_VA', 'Virginia_Beach_City_VA')
#location = 'Greenville_SC'
config_folder = 'Greenville_SC_original_configs'
county = gsub('.{3}$','',location)
county_config_ = paste0(county, '_', 'config', '_')


#######
#Check that config folder valid
#this also ensures that you are in the right folder to read data
#######

check_config_folder_valid(config_folder)

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

config_df_list[[2]][ , .(a = unique(num_polls), b = unique(num_residences)), by = descriptor]
#######
#Check result validity
#######

#This will return and descriptor case of inconsistency 
#(assuming that a config file has multiple counties)
bad_runs <- sapply(county, function(x){check_run_validity(config_df_list[[4]][grepl(x, descriptor), ])})

#remove any bad runs from the data
config_df_list <- lapply(config_df_list, function(x){x[!(descriptor %in% bad_runs), ]})

#######
#Constants for mapping
#######
#set result folder
result_folder = paste(location, 'results', sep = '_')

#get all file names the result_folder with the strings config_folder and 'residence_distances'
res_dist_list = list.files(result_folder)[grepl('residence_distances', list.files(result_folder))]
res_dist_list = res_dist_list[grepl(config_folder, res_dist_list)]

#get avg distance bounds for maps
if (length(county_config_ >1)){
county_config_ <- county_config_[1]} #cludge. Fix later
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
#TODO: Give Jenn config_df_list[[1]] for tableau work  
#plot_original(config_df_list[[1]], scale_bool = F)
#plot_original_pop_sized(config_df_list[[1]], conf_df_list[[2]])
pop_scaled_edes <- ede_with_pop(config_df_list)
#population scaled graph
plot_election_edes(pop_scaled_edes, suffix = 'pop_scaled')
#unscaled graph
plot_election_edes(config_df_list[[1]], suffix ='')

#########
#Make maps and cartograms
#########



mapply(function(x,y, z){make_bg_maps(x, 'map', result_folder_name = y, this_location = z)}, res_dist_list, result_folder, location)

mapply(function(x,y, z){make_demo_dist_map(x, 'white', result_folder_name = y, this_location = z)}, res_dist_list, result_folder, location)

mapply(function(x,y, z){make_demo_dist_map(x, 'black', result_folder_name = y, this_location = z)}, res_dist_list, result_folder, location)
