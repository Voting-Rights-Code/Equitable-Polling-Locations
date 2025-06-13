#######
#Analysis Constants
#######

#Basic constants for analysis
#LOCATION must be either a string or list of strings
#ORIG_CONFIG_FOLDER must be a string
#POTENTIAL_CONFIG_FOLDER must either be a string or NULL
#                   NULL indicates that this set of constants is only 
#                   on for historical

LOCATION = 'Muscogee_County_GA' #needed only for reading from csv and writing outputs
ORIG_CONFIG_FOLDER = "Muscogee_County_GA_original_configs"
POTENTIAL_CONFIG_FOLDER = "Muscogee_County_GA_log_configs" #leave NULL if only want historical analysis
ORIG_FIELD_OF_INTEREST = '' #must not leave empty if config set has only one element
POTENTIAL_FIELD_OF_INTEREST = '' #must not leave empty if config set has only one element

if (is.null(POTENTIAL_CONFIG_FOLDER)){
    HISTORICAL_FLAG = TRUE
}else{HISTORICAL_FLAG = FALSE}

DEMOGRAPHIC_LIST = c('white', 'black')

#Run-type specific constants
IDEAL_POLL_NUMBER  = 15 #the optimal number of polls desired for this county

#dictionary of custom descriptors
#keys: automatatically generated descriptor values to change
#values: the desired descriptor values
DESCRIPTOR_DICT_ORIG <- c('year_2020' = '2020', 'year_2022' = '2022', 'year_2024' = '2024')
DESCRIPTOR_DICT_POTENTIAL <- NULL

#If no changes desired, set 
#DESCRIPTOR_DICT <- NULL


#######
#Constants for DB
#######

# This is where this analysis will be stored in the cloud
STORAGE_BUCKET = 'equitable-polling-analysis'
if (HISTORICAL_FLAG){
    CLOUD_STORAGE_ANALYSIS_NAME = paste0(ORIG_CONFIG_FOLDER, 'HISTORICAL')
}else{
    CLOUD_STORAGE_ANALYSIS_NAME = paste0(ORIG_CONFIG_FOLDER, '_AND_', POTENTIAL_CONFIG_FOLDER)
}

#constants for reading data
READ_FROM_CSV = FALSE
PRINT_SQL = FALSE

#constants for database queries
#only need to define if READ_FROM_CSV = TRUE
PROJECT = "equitable-polling-locations"
DATASET = "equitable_polling_locations_prod"
BILLING = PROJECT

#Connect to database if needed
#returns NULL if READ_FROM_CSV = TRUE
POLLING_CON <- define_connection()
