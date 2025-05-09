library(data.table)
library(ggplot2)
library(stringr)
library(here)
library(plotly)
library(DBI)
library(bigrquery)
library(yaml)

#######
#DB connection
#Establishes Big query connection
#######
define_connection<- function(read_from_csv = READ_FROM_CSV, project = PROJECT, dataset = DATASET, billing = BILLING){
	if (!READ_FROM_CSV){
    	con <- dbConnect(
        	bigrquery::bigquery(),
        	project = PROJECT,
        	dataset = DATASET,
			billing = BILLING
    	)
	} else{ con = NULL}
	return(con)
}

#######
#Read config files from local directory or db
#The output of this process is a single data frame for each config_folder / config_set
#   the contains all the config values within.
#Note: the local directory structure is from before the dabase migration and 
#       the folder reorganization. It has not been fully tested.
#######

#The following set of functions is for formatting the .yaml files stored locally
#into a dataframe of config values, one for each config_folder 
#These are all called by read_config_folder_from_file and the function calls therein

config_to_list <- function(config_folder, config_name){
	#Reads yamls in config_folder, apppends config name as a field to yaml data
	config_file <- paste(config_folder, config_name, sep = '/')
	config_list <- read_yaml(config_file)
	if (!('config_name' %in% names(config_list))){ #without this if, config_name may appear twice
		config_list <- c(config_list, config_name = sub('.yaml', '', config_name))
	}
	return(config_list)
}

read_config_as_list <- function(config_folder){
	#returns a list of lists of all config files in config folder,
	#with the file name added as a field

	#get file names
	file_names <- list.files(config_folder)
	file_names<- file_names[grepl(".yaml$", file_names)]
	#then create a list of list
	config_list <- lapply(file_names, function(x){config_to_list(config_folder, x)})
	return(config_list)
}

check_config_file_fields <- function(config_list){
	#checks that a given list of config files all have the same set of fields
	#if yes, returns the fields. Otherwise, returns an error

	#fields for each config file
	fields <- unique(lapply(config_list, names))
	#raise error if each config file does not have the same content
	if (length(fields)!= 1){
		stop('Config files have different fields')
	}
	return(fields)
}

collapse_fields <- function(config){
	#In order to put the configs into a list, for each config field that is a list
	#turn it into a pipe separated string, also change NULLs to NAs

	#change nulls to NAs
	config <- lapply(config, function(x) {if(is.null(x)){x <- NA}else{x}})
	#collapse lists
	config <- lapply(config, function(x){paste(x[order(x)], collapse = '|')})
	return(config)
}

convert_configs_to_dt <- function(config_list){
	#check if each config in the list has the same fields
	fields <- check_config_file_fields(config_list)
	#collapse lists to strings
	collapsed_config_list <- lapply(config_list, function(x){collapse_fields(x)})
	#make this a data.table
	config_dt <- rbindlist(collapsed_config_list)
	return(config_dt)
}

#actual functions to read data from file or database

read_config_folder_from_file <- function(config_folder){
	#check that config_folder exists
	if (!dir.exists(config_folder)){
    	stop(paste('Config folder', config_folder, 'does not exist on file'))
	}
	#read config folder data from file
	config_list <- read_config_as_list(config_folder)
	config_dt <- convert_configs_to_dt(config_list)
	config_dt <- config_dt[ , config_set := config_folder]
	return(config_dt)
}

read_config_set_from_db <- function(config_set, columns, con=POLLING_CON){
	#read indicated columns from config set data in database
	comma_sep_colls = paste(columns, collapse = ',')
	sql <- paste0("SELECT ", comma_sep_colls, " FROM model_config_runs WHERE config_set =  '", config_set, "'")

	if (PRINT_SQL) print(sql)

	config_tbl <- dbGetQuery(con, sql)
	config_dt <- as.data.table(config_tbl)
	#check that this table is not empty
	if (nrow(config_dt) == 0){
		stop(paste('Config set', config_set, 'does not exist in database'))
	}
	return(config_dt)
}


#######
#Check that locations are in the indicated config set/folder
#Load the data if they are
#######

check_location_valid <- function(location, config_dt){
	#raise error if the config data does not pertain to the
	#given location
	locations_in_config_folder <- unique(config_dt$location)
	missing_locations <- setdiff(location, locations_in_config_folder)
	if (length(missing_locations)>0){
    	stop(paste('Given config folder does not contain data for the following location(s):', missing_locations))
	}
}

#Read in config data
load_config_data <- function(location, config_folder, read_from_csv = READ_FROM_CSV, con = POLLING_CON){
	#if config_folder is NULL, and HISTORIC_FLAG return NULL
	if(check_historic_flag(config_folder)){
		return(NULL)
	}
	if(read_from_csv){
		config_dt <- read_config_folder_from_file(config_folder)
	} else{
		config_dt <- read_config_set_from_db(config_folder, '*')
	}
	#then check that the location is in the data
	check_location_valid(location, config_dt)

	return(config_dt)
}
