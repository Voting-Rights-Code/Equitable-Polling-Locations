library(here)

#######
#Change directory
#######
setwd(here())

#######
#source functions
#######

source('result analysis/graph_functions.R')


#######
#Set Constants
#######
#Location must be part of config folder string

location = c('Fairfax_County_VA', 'Loudon_County_VA', 'Norfolk_City_VA', 'Virginia_Beach_City_VA')
config_folder = 'Engage_VA_2024_configs'
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

#######
#Check result validity
#######

#This will return and descriptor case of inconsistency 
#(assuming that a config file has multiple counties)
bad_runs <- sapply(county, function(x){check_run_validity(config_df_list[[4]][grepl(x, descriptor), ])})

#remove any bad runs from the data
config_df_list <- lapply(config_df_list, function(x){x[!(descriptor %in% bad_runs), ]})

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
