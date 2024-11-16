library(data.table)
library(here)
library(yaml)


get_location <- function(config_file, config_folder){
    file_name <- paste0(config_folder, '/', config_file)
    data = read_yaml(file_name)
    location <- data$location
    return(location)
}

get_driving <- function(config_file, config_folder){
    file_name <- paste0(config_folder, '/', config_file)
    data = read_yaml(file_name)
    if ('driving' %in% names(data)) {
        driving <- data$driving
    } else {
        driving <- FALSE
    }
    return(driving)
}

get_basenames_driving <- function(config_folder){
    config_files <- list.files(config_folder, '*.yaml')
    config_data <- data.table(file= config_files)
    config_data[ , folder:= config_folder <- sub('.','', config_folder)
            ][, location:= lapply(file, function(x){get_location(x, config_folder)})
            ][, driving := sapply(file, function(x){get_driving(x, config_folder)})
            ][, result_folder := paste0(location, '_results')
            ][, file_base_name := paste0(result_folder, folder, '.', file)
            ][, file_base_name := gsub('.yaml', '', file_base_name)]
    
    return(config_data[, .(file_base_name, driving)])
}

add_source_value <- function(filename_base, result_type, source_value){
    result_name <- paste0(filename_base, '_', result_type, '.csv')
    dt <- fread(result_name)
    dt[, source:= source_value]
    fwrite(dt, result_name)
}

adapt_result_datasets <- function(filename_base, driving){
    result_dt_name <- paste0(filename_base, '_result.csv')
    if (file.exists(result_dt_name)){
        result_dt <- fread(result_dt_name)

        if (is.na(driving) | !(driving)){
            result_dt[ , source:= 'haversine distance']
        } else{ 
            result_dt[ , source:= 'driving distance'] 
        }
        source_value <- unique(result_dt$source)
        fwrite(result_dt, result_dt_name)

        result_types <- c('precinct_distances', 'residence_distances', 'edes')
        sapply(result_types, function(x){add_source_value(filename_base, x, source_value)})
    } else{
        if (file.exists('configs_without_results.txt')){
            write(filename_base, file = 'configs_without_results.txt', append = TRUE)
        } else{
            cat(filename_base, file = 'configs_without_results.txt',sep="\n")
        }
    }
}

#add source column to/ remove haversine_m from result files
all_folders <- list.dirs('.', recursive = FALSE)
config_folders <- all_folders[grepl('configs', all_folders)]
config_folders <- config_folders[!(grepl('test', config_folders))]
dt_list <- lapply(config_folders, get_basenames_driving)
#get rid of empty data
dt_list_rows <- sapply(dt_list, nrow)
dt_list_good <- dt_list[dt_list_rows >0]

dt <- do.call(rbind, dt_list_good)
mapply(function(file, driving) {adapt_result_datasets(file, driving)}, dt$file_base_name, dt$driving)
