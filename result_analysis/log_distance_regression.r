library(here)
library(reticulate)
#use_condaenv('C:/Users/ganga/anaconda3/envs/equitable-polls', required = TRUE)

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

#######
#Set Constants
#######

#Basic constants for analysis
#LOCATION must be either a string or list of strings
#CONFIG_FOLDER must be a string

LOCATION = c('Berkeley_County_SC','Greenville_County_SC', 'Lexington_County_SC','Richland_County_SC', 'York_County_SC') #needed only for reading from csv and writing outputs
#list of config folders to compare.
#MUST 
# * be of the same locations
CONFIG_FOLDER = c('Berkeley_County_SC_original_configs','Greenville_County_SC_original_configs', 'Lexington_County_SC_original_configs','Richland_County_SC_original_configs', 'York_County_SC_original_configs')
FIELDS_OF_INTEREST_LIST = c('', '', '', '', '') #must not leave empty if config set has only one element

# This is where this analysis will be stored in the cloud
STORAGE_BUCKET = 'equitable-polling-analysis'
CLOUD_STORAGE_ANALYSIS_NAME = paste0(CONFIG_FOLDER, collapse = '_AND_') 

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
#if (!READ_FROM_CSV){
#    system("gcloud auth application-default login")
#}

#######
#Check that location and folders valid
#Load configs and get driving flags
#######

#Load config data
#checking if the config folder is valid
#and that the location is in the indicated dataset
config_dt_list <- mapply(function(location, folder){load_config_data(location, folder)}, LOCATION, CONFIG_FOLDER, SIMPLIFY = FALSE)

#######
#Read in data
#Run this for each of the folders under consideration
#Recall, output of form: list(ede_df, precinct_df, residence_df, result_df)
#######

#names of the output data in these lists
#come from TABLES above

output_df_list <- mapply(function(config_dt, field_of_interest){read_result_data(config_dt, field_of_interest)}, config_dt_list, FIELDS_OF_INTEREST_LIST, SIMPLIFY = FALSE)
names(output_df_list) <- CONFIG_FOLDER
#output_df_list <- unlist(output_df_list, recursive = FALSE)


#get data to run regression

regression_data <- mapply(function(location, output){get_regression_data(location, output[[4]])}, LOCATION, output_df_list, SIMPLIFY = FALSE)
##descriptor_list <- unique(regression_data$descriptor)
#reference <- descriptor_list[grepl(REFERENCE_TAG, descriptor_list)]
##regression_data <- calculate_pct_change(regression_data, reference)

# #run regeression by descriptor and store coefs in a data frame
run_distance_model <- function(regression_data){
    distance_model <- regression_data[, as.list(coef(lm(distance_m ~ pop_density_km  + pct_black + pop_density_km*pct_black),  weights = population )), by = descriptor]
    setnames(distance_model, c('(Intercept)', 'pop_density_km', 'pct_black','pop_density_km:pct_black'), c('intercept', 'density_coef', 'pct_black_coef', 'density_black_interaction_coef'))
    # #fwrite(distance_model, paste0(COUNTY, '_distance_model.csv'))
}
distance_model_list <- lapply(regression_data, function(x) run_distance_model(x))

# change_model<- regression_data[, as.list(coef(lm(pct_extra_in_2022 ~ pop_density_km  + pct_black + pop_density_km*pct_black),  weights = population )), by = descriptor]
# setnames(change_model, c('(Intercept)', 'pop_density_km', 'pct_black','pop_density_km:pct_black'), c('intercept', 'density_coef', 'pct_black_coef', 'density_black_interaction_coef'))
# #fwrite(change_model, paste0(COUNTY, '_pct_change_model.csv'))

# #run regeression by descriptor and store coefs in a data frame
run_naive_distance_model <- function(regression_data){
    distance_model <- regression_data[, as.list(coef(lm(distance_m ~ pop_density_km),  weights = population )), by = descriptor]
    setnames(distance_model, c('(Intercept)', 'pop_density_km'), c('intercept', 'density_coef'))
    # #fwrite(distance_model, paste0(COUNTY, '_distance_model.csv'))
}

# #run regeression by descriptor and store coefs in a data frame
run_distance_model_resid <- function(regression_data){
    distance_model <- regression_data[, as.list(coef(lm((distance_m - (intercept + density_coef*pop_density_km)) ~  pct_black),  weights = population )), by = descriptor]
#    setnames(distance_model, c('(Intercept)', 'pop_density_km', 'pct_black','pop_density_km:pct_black'), c('intercept', 'density_coef', 'pct_black_coef', 'density_black_interaction_coef'))
    # #fwrite(distance_model, paste0(COUNTY, '_distance_model.csv'))
}


run_naive_distance_model_resid <- function(regression_data){
    distance_model <- regression_data[, as.list(resid(lm(distance_m ~ pop_density_km),  weights = population )), by = descriptor]
#    setnames(distance_model, c('(Intercept)', 'pop_density_km'), c('intercept', 'density_coef'))
    # #fwrite(distance_model, paste0(COUNTY, '_distance_model.csv'))
}

naive_distance_list <- lapply(regression_data, function(x) run_naive_distance_model(x))

naive_distance_resid_list <- lapply(regression_data, function(x) run_naive_distance_model_resid(x))


regression_data_naive_dist <- mapply(function(regression, naive) merge(regression, naive, by = c('descriptor') ), regression_data, naive_distance_list, SIMPLIFY = FALSE)
#regression_data_naive_dist <- mapply(function(regression, naive) merge(regression, naive, by = c('descriptor') ), regression_data_naive_dist, naive_distance_resid_list, SIMPLIFY = FALSE)


distance_model_list <- lapply(regression_data_naive_dist, function(x) run_distance_model_resid(x))

bg_data <- function(density_data){
    density_data[ , `:=`(white_weighted_dist = white*distance_m, black_weighted_dist = black *distance_m)
                    ][, id_bg := gsub('.{3}$', '', density_data$id_orig)][, year := unlist(year)]
    
    bg_result_df <- density_data[ , .(population = sum(population), white = sum(white), black = sum(black), area= sum(area),
									weighted_dist = sum(weighted_dist), white_weighted_dist = sum(white_weighted_dist), 
                                    black_weighted_dist = sum(black_weighted_dist)), by=list(id_bg, year)
								][ , `:=`(pop_avg_dist = weighted_dist/population, white_avg_dist = white_weighted_dist/white, black_avg_dist = black_weighted_dist/black, pop_density_km = 1e6 *population/area)
                                ][, white_minus_black_avg_diff := white_avg_dist - black_avg_dist
                                ][, white_minus_black_wgtd_diff := white_weighted_dist - black_weighted_dist
                                ]
    melt_bg_avg_dist <- melt(bg_result_df, id.vars = c('id_bg', 'year', 'pop_density_km'), measure.vars = list(c( 'white_avg_dist', 'black_avg_dist', 'white_weighted_dist', 'black_weighted_dist'), c('white', 'black', 'white', 'black')), value.name = c('dist', 'demo_pop'), variable.name = 'demo_avg_dist')[, demo_avg_dist:=factor(demo_avg_dist, labels = c( 'white_avg_dist', 'black_avg_dist', 'white_weighted_dist', 'black_weighted_dist'))]
    #setnames(melt_bg_avg_dist, c('variable'), c('demo_avg_dist'))
    return(list(melt_bg_avg_dist, bg_result_df))
}

bg_density_data <- lapply(regression_data, function(density){bg_data(density)})

head(bg_density_data[[1]][[1]])
county = 'Greenville_County_SC'
year_str = '2018'

ggplot(bg_density_data[[county]][[1]][year == year_str & demo_avg_dist %in% c('white_weighted_dist',
'black_weighted_dist'), ] , aes(x = pop_density_km, y = dist, group = demo_avg_dist, color = demo_avg_dist, size = demo_pop )) +
geom_point() + geom_smooth(method=loess, aes(group=demo_avg_dist)) + 
labs(title = paste("Total White and Black population distance to polls by block group", county, year_str))

ggplot(bg_density_data[[county]][[1]][year == year_str & demo_avg_dist %in% c('white_avg_dist', 'black_avg_dist'), ] , aes(x = pop_density_km, y = dist, group = demo_avg_dist, color = demo_avg_dist, size = demo_pop )) +
geom_point() + geom_smooth(method=loess, aes(group=demo_avg_dist)) + 
labs(title = paste("White and Black population distance to polls by block group", county, year_str))


ggplot(bg_density_data[[county]][[2]][year == '2020' & pop_density_km <2000 & pop_density_km > 200, ] , aes(x = pop_density_km, y = white_minus_black_wgtd_diff )) +
geom_point() + geom_smooth(method=lm) + labs(title = paste("Difference in total distance traveled by White and, Black population to polls by block group"), county, year_str)

ggplot(bg_density_data[[county]][[2]][year == '2020' & pop_density_km <2000 & pop_density_km > 200, ] , aes(x = pop_density_km, y = white_minus_black_avg_diff )) +
geom_point() + geom_smooth(method=lm) + labs(title = paste("Difference in avg distance traveled by White and Black population to polls by block group"), county, year_str)
