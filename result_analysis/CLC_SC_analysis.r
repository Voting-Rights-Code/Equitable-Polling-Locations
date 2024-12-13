#######
#NOTE: this file is deprecated. It is not compatible with the new graph_functions
#structure that reads data from the config files
#######

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
LOCATION = 'York_County_SC'
CONFIG_FOLDER = 'York_County_SC_original_configs'

# This is where this analysis will be stored
STORAGE_BUCKET = 'equitable-polling-analysis'
CLOUD_STORAGE_ANALYSIS_NAME = deparse(substitute(current_file))

#Run-type specific constants
REFERENCE_TAG = '2022' #Reference year for analysis

#constants for reading data
READ_FROM_CSV = FALSE

#constants for database queries
#only need to define if READ_FROM_CSV = TRUE
PROJECT = "equitable-polling-locations"
DATASET = "scratch_chad2"
BILLING = PROJECT

#Connect to database if needed
#returns NULL if READ_FROM_CSV = TRUE
POLLING_CON <- define_connection()


#######
#Check that location and folders valid
#this also ensures that you are in the right folder to read data
#######

#Does the config folder exist?
check_config_folder_valid(CONFIG_FOLDER)
#Does the config folder contain files associated to the location
# check_location_valid(LOCATION, CONFIG_FOLDER)


#######
#Read in data
#Run this for each of the folders under consideration
#Recall, output of form: list(ede_df, precinct_df, residence_df, result_df)
#######
config_df_list <- read_result_data(LOCATION, CONFIG_FOLDER, 'historical')
#config_ede_df<- config_df_list[[1]]
#config_precinct_df<- config_df_list[[2]]
#config_residence_df<- config_df_list[[3]]
#config_result_df<- config_df_list[[4]]

#config_df_list[[2]][ , .(a = unique(num_polls), b = unique(num_residences)), by = descriptor]


#######
#Constants for mapping
#######
#set result folder
result_folder = paste(LOCATION, 'results', sep = '_')

#get all file names the result_folder with the strings CONFIG_FOLDER and 'residence_distances'
res_dist_list = list.files(result_folder)[grepl('residence_distances', list.files(result_folder))]
res_dist_list = res_dist_list[grepl(CONFIG_FOLDER, res_dist_list)]

#get avg distance bounds for maps
color_bounds <- distance_bounds(LOCATION, CONFIG_FOLDER)


#######
#Plot data
#######
plot_folder = paste0('result_analysis/', CONFIG_FOLDER)
if (file.exists(file.path(here(), plot_folder))){
    setwd(file.path(here(), plot_folder))
} else{
    dir.create(file.path(here(), plot_folder))
    setwd(file.path(here(), plot_folder))
}


#Plot the edes for all runs in original_location and equivalent optimization runs by demographic

#join ede data with population data for scaling
pop_scaled_edes <- ede_with_pop(config_df_list)
#population scaled graph
plot_historic_edes(CONFIG_FOLDER, pop_scaled_edes, suffix = 'pop_scaled')
#unscaled graph
plot_historic_edes(CONFIG_FOLDER, config_df_list[[1]], suffix ='')

#########
#Make maps and cartograms
#########

#Choosing not to do cartograms because of convergence difficulties

mapply(function(x,y, z){make_bg_maps(CONFIG_FOLDER, x, 'map', result_folder_name = y, this_location = z)}, res_dist_list, result_folder, LOCATION)

#mapply(function(x,y, z){make_bg_maps(CONFIG_FOLDER, x, 'cartogram', result_folder_name = y, this_location = z)}, res_dist_list, result_folder, LOCATION)

mapply(function(x,y, z){make_demo_dist_map(CONFIG_FOLDER, x, 'white', result_folder_name = y, this_location = z)}, res_dist_list, result_folder, LOCATION)

mapply(function(x,y, z){make_demo_dist_map(CONFIG_FOLDER, x, 'black', result_folder_name = y, this_location = z)}, res_dist_list, result_folder, LOCATION)

mapply(function(x,y, z){make_demo_dist_map(CONFIG_FOLDER, x, 'population', result_folder_name = y, this_location = z)}, res_dist_list, result_folder, LOCATION)


#####CAUTION: DELIVERED PLOT, BUT EXPERIMENTAL######


#3d Plot pct distance changed by density and black
regression_data <- get_regression_data(LOCATION, config_df_list[[4]])
descriptor_list <- unique(regression_data$descriptor)
reference <- descriptor_list[grepl(REFERENCE_TAG, descriptor_list)]
regression_data <- calculate_pct_change(regression_data, reference)


sapply(descriptor_list[descriptor_list != reference], function(x){plot_pct_change_by_density_black_3d(regression_data, x)})

upload_graph_files_to_cloud_storage()

#####STOP HERE######
#####REGRESSION FUNCTIONS AFTER THIS MAY NOT WORK AS DESIRED######


# #######
# #Regression work
# #######

# #get data to run regression

# regression_data <- get_regression_data(LOCATION, config_df_list[[4]])
# descriptor_list <- unique(regression_data$descriptor)
# reference <- descriptor_list[grepl(REFERENCE_TAG, descriptor_list)]
# regression_data <- calculate_pct_change(regression_data, reference)

# #run regeression by descriptor and store coefs in a data frame
# distance_model <- regression_data[, as.list(coef(lm(distance_m ~ pop_density_km  + pct_black + pop_density_km*pct_black),  weights = population )), by = descriptor]
# setnames(distance_model, c('(Intercept)', 'pop_density_km', 'pct_black','pop_density_km:pct_black'), c('intercept', 'density_coef', 'pct_black_coef', 'density_black_interaction_coef'))
# #fwrite(distance_model, paste0(COUNTY, '_distance_model.csv'))

# change_model<- regression_data[, as.list(coef(lm(pct_extra_in_2022 ~ pop_density_km  + pct_black + pop_density_km*pct_black),  weights = population )), by = descriptor]
# setnames(change_model, c('(Intercept)', 'pop_density_km', 'pct_black','pop_density_km:pct_black'), c('intercept', 'density_coef', 'pct_black_coef', 'density_black_interaction_coef'))
# #fwrite(change_model, paste0(COUNTY, '_pct_change_model.csv'))

# #plot predicted distances at a given density
# #plot_predicted_distances(regression_data, distance_model)

# #2d Plot actual distances by density and black
# #sapply(descriptor_list, function(x){plot_distance_by_density_black(regression_data, x)})

# #3d Plot actual distances by density and black
# #sapply(descriptor_list, function(x){plot_distance_by_density_black_3d(regression_data, x)})




# location_list = c('Berkeley', 'Greenville', 'Lexington', 'Richland', 'York')
# file_list = sapply(location_list, function(x)paste0('../', x, '_SC_original_configs/', x, '_pct_change_model.csv'))
# dt_list <- lapply(file_list, fread)
# dt <- do.call(rbind, dt_list)

# within_grp_ineq <- pop_scaled_edes[, ratio:= y_EDE/avg_dist
#             ][, c('descriptor', 'demographic', 'ratio')
#             ][order(ratio)]

# foo <- lm(pct_white ~ pop_density_km, regression_data)
# summary(foo)

# cor(regression_data$pct_white, regression_data$pop_density_km)

# quantile(regression_data$pop_density_km)

# head(pop_scaled_edes[demographic == 'population', c('descriptor', 'num_polls', 'avg_dist')])
# low_year = '2016'
# avg_low = pop_scaled_edes[grepl(low_year, descriptor), ]$avg_dist
# avg_high = pop_scaled_edes[grepl('2022', descriptor), ]$avg_dist
# bar <- pop_scaled_edes[grepl(low_year, descriptor), c('demographic')][ , difference:= avg_high-avg_low]
# head(bar)

# dt[descriptor == paste(COUNTY, low_year, sep = '_'), ]

