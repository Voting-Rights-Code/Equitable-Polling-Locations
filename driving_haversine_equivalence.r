library(data.table)
library(here)
library(yaml)

adapt_big_dataset <- function(location){
    file_name <- paste0('datasets/polling/', location, '/', location, '.csv')
    dt <- fread(file_name)
    if ('source' %in% names(dt)){ #remove haversine
        dt[ , haversine_m := NULL] 
    } else{ #add source
        dt[ , source:= 'haversine distance']
    }
    fwrite(dt, file_name)
}

get_location <- function(config_file, config_folder){
    file_name <- paste0(config_folder, '/', config_file)
    data = read_yaml(file_name)
    location <- data$location
    return(location)
}

get_basenames <- function(config_folder){
    config_files <- list.files(config_folder, '*.yaml')
    config_data <- data.table(file= config_files)
    config_data[ , folder:= config_folder <- sub('.','', config_folder)
            ][, location:= lapply(file, function(x){get_location(x, config_folder)})
            ][, result_folder := paste0(location, '_results')
            ][, file_base_name := paste0(result_folder, folder, '.', file)
            ][ , file_base_name := gsub('.yaml', '', file_base_name)]
    return(config_data$file_base_name)
}

add_source_value <- function(filename_base, result_type, source_value){
    result_name <- paste0(filename_base, '_', result_type, '.csv')
    dt <- fread(result_name)
    dt[, source:= source_value]
    fwrite(dt, result_name)
}

adapt_result_datasets <- function(filename_base){
    result_dt_name <- paste0(filename_base, '_result.csv')
    result_dt <- fread(result_dt_name)
    if ('source' %in% names(dt)){ #remove haversine
        result_dt[ , haversine_m := NULL] 
    } else{ #add source
        result_dt[ , source:= 'haversine distance']
    }
    source_value <- unique(result_dt$source)
    
    fwrite(result_dt, result_dt_name)
    result_types <- c('precinct_distances', 'residence_distances', 'edes')
    sapply(result_types, function(x){add_source_value(filename_base, x, source_value)})
}

#add source column to/ remove haversine_m from big file
#location_list = list.dirs('datasets/polling', recursive = FALSE)
#sapply(location_list, function(x){adapt_big_dataset(x)})

#add source column to/ remove haversine_m from result files
all_folders <- list.dirs('.', recursive = FALSE)
config_folders <- all_folders[grepl('configs', all_folders)]
all_base_names <- unlist(sapply(config_folders, get_basenames))
adapt_result_datasets(all_base_names[1])
