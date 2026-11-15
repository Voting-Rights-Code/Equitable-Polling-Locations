#######
#Analysis Constants
#######

#Basic constants for analysis
#LOCATION must be either a string or list of strings
#ORIG_CONFIG_FOLDER must be a string
#POTENTIAL_CONFIG_FOLDER must either be a string or NULL
#                   NULL indicates that this set of constants is only
#                   on for historical


LOCATION = 'Monongalia_County_WV' #needed only for reading from csv and writing outputs
ORIG_CONFIG_FOLDER = "Monongalia_County_WV_driving_original_configs"
POTENTIAL_CONFIG_FOLDER = NULL #leave NULL if only want historical analysis
ORIG_FIELD_OF_INTEREST = '' #must not leave empty if config set has only one element
POTENTIAL_FIELD_OF_INTEREST = '' #must not leave empty if config set has only one element

if (is.null(POTENTIAL_CONFIG_FOLDER)){
    HISTORICAL_FLAG = TRUE
}else{HISTORICAL_FLAG = FALSE}

DEMOGRAPHIC_LIST = c('white', 'black')

#Run-type specific constants
#24 = unique id_dest count in the metric_driving_time results CSV (matches the
#24 dissolved features in the solver precinct shapefile built from it)
IDEAL_POLL_NUMBER  = 24

#dictionary of custom descriptors
#keys: automatatically generated descriptor values to change
#values: the desired descriptor values
#If no changes desired, set
DESCRIPTOR_DICT_ORIG <-NULL
DESCRIPTOR_DICT_POTENTIAL <- NULL


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

#Connect to database if needed
#returns NULL if READ_FROM_CSV = TRUE
POLLING_CON <- define_connection()


#constants for how graphs and maps should be made
LINEAR_COLOR_GRADIENT = FALSE #should the maps have a log or linear color scale
