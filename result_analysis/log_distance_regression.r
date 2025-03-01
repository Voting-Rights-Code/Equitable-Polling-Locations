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
    #density_data[ , `:=`(white_weighted_dist = white*distance_m, black_weighted_dist = black *distance_m)
    #                ][, id_bg := gsub('.{3}$', '', density_data$id_orig)]
    
    density_data[ , avg_distance := weighted_dist/population]
    
    density_data_long <- melt(density_data, id.vars = c('id_orig', 'descriptor', 'pop_density_km','avg_distance', 'area'), measure.vars = c("population", "hispanic","non_hispanic", "white", "black", "native", "asian", "pacific_islander", "other"), value.name ='demo_pop' , variable.name = "demographic")
    
    density_data_long[ , demo_weighted_dist := demo_pop * avg_distance
                    ][, id_bg := gsub('.{3}$', '', density_data_long$id_orig)]
    

    bg_result_df <- density_data_long[ , .(demo_pop = sum(demo_pop), area= sum(area),
									demo_weighted_dist = sum(demo_weighted_dist)),  by=list(id_bg, descriptor, demographic)
								][ , demo_avg_dist := demo_weighted_dist/demo_pop]
    descriptor1 <- unique(bg_result_df$descriptor)[1]
    bg_pop_density <- bg_result_df[demographic == 'population' & descriptor ==
                    descriptor1, ][, pop_density_km := 1e6 *demo_pop/area]
    bg_result_df<- merge(bg_result_df, bg_pop_density[ , .(id_bg, pop_density_km)], by = c('id_bg'))

    return(bg_result_df)
}

bg_density_demo <- lapply(regression_data, function(density){bg_data(density)})



make_plots <- function(bg_density_demo, county){
ggplot(bg_density_data[[county]][descriptor == descriptor_str, ] , aes(x = pop_density_km, y = dist, group = demographic, color = demographic, size = demo_pop )) +
geom_point() + geom_smooth(method=lm, mapping = aes(weight = demo_pop), se= F) + scale_x_continuous(trans = 'log10') + scale_y_continuous(trans = 'log10') + 
labs(title = paste("Demographic average distance to polls by block group", county, year_str))
output = paste(county, descriptor_str, "avg distance.png")
ggsave(output)


}


county_list = c('Berkeley_County_SC', 'Greenville_County_SC', 'Lexington_County_SC', 'Richland_County_SC', 'York_County_SC')
year_list = c('2014', '2016', '2018', '2020', '2022')

sapply(year_list, function(year){make_plots(bg_density_data, 'Berkeley_County_SC', year)})
sapply(year_list, function(year){make_plots(bg_density_data, 'Greenville_County_SC', year)})
sapply(year_list, function(year){make_plots(bg_density_data, 'Lexington_County_SC', year)})
sapply(year_list, function(year){make_plots(bg_density_data, 'Richland_County_SC', year)})
sapply(year_list, function(year){make_plots(bg_density_data, 'York_County_SC', year)})
