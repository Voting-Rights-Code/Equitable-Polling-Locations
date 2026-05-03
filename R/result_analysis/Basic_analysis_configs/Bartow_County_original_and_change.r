#######
#Analysis Constants
#######

#Basic constants for analysis
#LOCATION must be either a string or list of strings
#ORIG_CONFIG_FOLDER must be a string
#POTENTIAL_CONFIG_FOLDER must either be a string or NULL
#                   NULL indicates that this set of constants is only 
#                   on for historical


LOCATION = 'Bartow_County_GA' #needed only for reading from csv and writing outputs
ORIG_CONFIG_FOLDER = "Bartow_County_GA_original_configs"
POTENTIAL_CONFIG_FOLDER = 'Bartow_County_GA_change_locations_configs' #leave NULL if only want historical analysis
ORIG_FIELD_OF_INTEREST = 'year' #must not leave empty if config set has only one element
POTENTIAL_FIELD_OF_INTEREST = '' #must not leave empty if config set has only one element

if (is.null(POTENTIAL_CONFIG_FOLDER)){
    HISTORICAL_FLAG = TRUE
}else{HISTORICAL_FLAG = FALSE}

DEMOGRAPHIC_LIST = c('white', 'black')

#Run-type specific constants
IDEAL_POLL_NUMBER  = 17 #the optimal number of polls desired for this county

#dictionary of custom descriptors
#keys: automatatically generated descriptor values to change
#values: the desired descriptor values
#eg
#DESCRIPTOR_DICT_ORIG <- c('year_2014' = '2014', 'year_2016' = '2016', 
                     #'year_2018' = '2018', 'year_2020' = '2020', 
                     #'year_2022' = '2022')
#If no changes desired, set 
DESCRIPTOR_DICT_ORIG <-NULL
DESCRIPTOR_DICT_POTENTIAL <- c('maxpctnew_0.0589' = 'change_1', 'maxpctnew_0.1177' = 'change_2', 'maxpctnew_0.1765' = 'change_3',
                            'maxpctnew_0.2353' = 'change_4', 'maxpctnew_0.2942' = 'change_5', 'maxpctnew_0.353' = 'change_6',
                            'maxpctnew_0.4118' = 'change_7', 'maxpctnew_0.4706' = 'change_8', 'maxpctnew_0.5295' = 'change_9',
                            'maxpctnew_0.5883' = 'change_10', 'maxpctnew_0.6471' = 'change_11', 'maxpctnew_0.7059' = 'change_12',
                            'maxpctnew_0.7648' = 'change_13', 'maxpctnew_0.8236' = 'change_14', 'maxpctnew_0.8824' = 'change_15',
                            'maxpctnew_0.9412' = 'change_16', 'maxpctnew_1' = 'change_17')


#######
#Constants for DB
#######

# This is where this analysis will be stored in the cloud
STORAGE_BUCKET = 'equitable-polling-analysis'
if (HISTORICAL_FLAG){
    CLOUD_STORAGE_ANALYSIS_NAME = paste(ORIG_CONFIG_FOLDER, 'HISTORICAL')
}else{
    CLOUD_STORAGE_ANALYSIS_NAME = paste0(ORIG_CONFIG_FOLDER, '_AND_', POTENTIAL_CONFIG_FOLDER)
}

#constants for reading data
READ_FROM_CSV = TRUE
PRINT_SQL = FALSE

#constants for database queries
#only need to define if READ_FROM_CSV = FALSE
PROJECT = "equitable-polling-locations"
DATASET = "equitable_polling_locations_prod"
BILLING = PROJECT

#Connect to database if needed
#returns NULL if READ_FROM_CSV = TRUE
POLLING_CON <- define_connection()


#constants for how graphs and maps should be made
LINEAR_COLOR_GRADIENT = FALSE #should the maps have a log or linear color scale
