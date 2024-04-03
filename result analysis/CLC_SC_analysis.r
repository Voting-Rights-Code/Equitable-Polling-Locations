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

#location = c('Fairfax_County_VA', 'Loudon_County_VA', 'Norfolk_City_VA', 'Virginia_Beach_City_VA')
#config_folder = 'Engage_VA_2024_driving_configs'
location = 'York_SC'
config_folder = 'York_SC_original_configs'
reference_tag = '2022'
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

#mapply(function(x,y, z){make_bg_maps(x, 'cartogram', result_folder_name = y, this_location = z)}, res_dist_list, result_folder, location)

mapply(function(x,y, z){make_demo_dist_map(x, 'white', result_folder_name = y, this_location = z)}, res_dist_list, result_folder, location)

mapply(function(x,y, z){make_demo_dist_map(x, 'black', result_folder_name = y, this_location = z)}, res_dist_list, result_folder, location)

mapply(function(x,y, z){make_demo_dist_map(x, 'population', result_folder_name = y, this_location = z)}, res_dist_list, result_folder, location)



#######
#Regression work
#######

#get data to run regression

regression_data <- get_regression_data(location, config_df_list[[4]])
descriptor_list <- unique(regression_data$descriptor)
reference <- descriptor_list[grepl(reference_tag, descriptor_list)]
regression_data <- calculate_pct_change(regression_data, reference)

#run regeression by descriptor and store coefs in a data frame
distance_model <- regression_data[, as.list(coef(lm(distance_m ~ pop_density_km  + pct_black + pop_density_km*pct_black),  weights = population )), by = descriptor]
setnames(distance_model, c('(Intercept)', 'pop_density_km', 'pct_black','pop_density_km:pct_black'), c('intercept', 'density_coef', 'pct_black_coef', 'density_black_interaction_coef'))
#fwrite(distance_model, paste0(county, '_distance_model.csv'))

change_model<- regression_data[, as.list(coef(lm(pct_extra_in_2022 ~ pop_density_km  + pct_black + pop_density_km*pct_black),  weights = population )), by = descriptor]
setnames(change_model, c('(Intercept)', 'pop_density_km', 'pct_black','pop_density_km:pct_black'), c('intercept', 'density_coef', 'pct_black_coef', 'density_black_interaction_coef'))
#fwrite(change_model, paste0(county, '_pct_change_model.csv'))

#plot predicted distances at a given density
#plot_predicted_distances(regression_data, distance_model)

#2d Plot actual distances by density and black
#sapply(descriptor_list, function(x){plot_distance_by_density_black(regression_data, x)})

#3d Plot actual distances by density and black
#sapply(descriptor_list, function(x){plot_distance_by_density_black_3d(regression_data, x)})


#3d Plot pct distance changed by density and black
sapply(descriptor_list[descriptor_list != reference], function(x){plot_pct_change_by_density_black_3d(regression_data, x)})
    

location_list = c('Berkeley', 'Greenville', 'Lexington', 'Richland', 'York')
file_list = sapply(location_list, function(x)paste0('../', x, '_SC_original_configs/', x, '_pct_change_model.csv'))
dt_list <- lapply(file_list, fread)
dt <- do.call(rbind, dt_list)

within_grp_ineq <- pop_scaled_edes[, ratio:= y_EDE/avg_dist
            ][, c('descriptor', 'demographic', 'ratio')
            ][order(ratio)]

foo <- lm(pct_white ~ pop_density_km, regression_data)
summary(foo)

cor(regression_data$pct_white, regression_data$pop_density_km)

quantile(regression_data$pop_density_km)

head(pop_scaled_edes[demographic == 'population', c('descriptor', 'num_polls', 'avg_dist')])
low_year = '2016'
avg_low = pop_scaled_edes[grepl(low_year, descriptor), ]$avg_dist
avg_high = pop_scaled_edes[grepl('2022', descriptor), ]$avg_dist
bar <- pop_scaled_edes[grepl(low_year, descriptor), c('demographic')][ , difference:= avg_high-avg_low]
head(bar)

dt[descriptor == paste(county, low_year, sep = '_'), ]

