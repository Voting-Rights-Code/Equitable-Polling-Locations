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
config_folder = 'Engage_VA_2024_driving_configs'
#location = 'Greenville_SC'
#config_folder = 'Greenville_SC_original_configs'
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
if (length(county_config_) >1){
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

mapply(function(x,y, z){make_demo_dist_map(x, 'population', result_folder_name = y, this_location = z)}, res_dist_list, result_folder, location)


#######
#Regression work
#######

map_folders <- paste0('../../datasets/census/tiger/', location, '/')
map_files <- paste0(map_folders, list.files(map_folders)[endsWith(list.files(map_folders), 'tabblock20.shp')])

map_data<- lapply(map_files, st_read)
block_areas <- lapply(map_data, function(x){x[, c('GEOID20', 'ALAND20', 'AWATER20')]})
if (length(block_areas)> 1){
    block_areas <- do.call(rbind, block_areas)
}

regression_data <- merge(config_df_list[[4]], block_areas, by.x = 'id_orig', by.y = 'GEOID20', all.x = T)
regression_data[ , `:=`(pop_density_m = population/(ALAND20 + AWATER20), pop_density_km = 1e6 *population/(ALAND20 + AWATER20),dist_m = Weighted_dist/ population, pct_white= 100 * white/population, pct_black = 100 *black/population)]

model1 <- lm(dist_m ~ pop_density_km + white + black, data = regression_data, weights = population )
model2 <- lm(Weighted_dist ~ pop_density + pct_white + pct_black, data = regression_data)

dt1 <- regression_data[pop_density_km >64 , as.list(coef(lm(dist_m ~ pop_density_km + white + black,  weights = population ))), by = descriptor]
dt1.1 <- regression_data[pop_density_km >64 , as.list(coef(lm(dist_m ~ pop_density_km + pct_white + pct_black,  weights = population ))), by = descriptor]
dt1.2 <- regression_data[pop_density_km >64 , as.list(coef(lm(dist_m ~ pop_density_km + pct_white,  weights = population ))), by = descriptor]
dt2m <- regression_data[ , as.list(coef(lm(Weighted_dist ~ pop_density_m + pct_white + pct_black ))),  by = descriptor]
dt2km <- regression_data[ , as.list(coef(lm(Weighted_dist ~ pop_density_km + pct_white + pct_black ))),  by = descriptor]

head(dt1)
head(dt1.1)
head(dt1.2)

head(dt2m)
head(dt2km)
