library(data.table)
library(here)

setwd(here())

state <- "SC"
county_list <- c("Greenville", "Lexington", "Richland", "York")
lat_lon_file_name <- paste(county_list, state, 'addresses_out.csv', sep='_')
lat_lon_folder <- paste('../voting_data/data', state, county_list, sep= '/' )  
lat_lon_path <- paste(lat_lon_folder, lat_lon_file_name, sep = '/')
lat_lon_data<- lapply(lat_lon_path, fread)

polling_location <- paste(county_list, state, sep='_')
polling_file_name <- paste(polling_location, 'locations_only.csv', sep='_')
polling_folder <- paste('datasets/polling', polling_location, sep= '/')
polling_path <- paste(polling_folder, polling_file_name, sep= '/')
polling_data<-lapply(polling_path, fread)

#instead of merging the two, the lat_lon is the most up to date 
#(some addresses have been changed during manual verification)
#just overwrite the polling data with the corresponding files.

bad_cols <- names(lat_lon_data[[1]])[4:11]
lat_lon_copy <- copy(lat_lon_data)
lat_lon_data<- lapply(lat_lon_data, function(x){x[ , (bad_cols):= NULL]})
lapply(lat_lon_data, function(x){setnames(x, names(x), c('Location', 'Address', 'Location type', 'Latitude', 'Longitude'))})
lat_lon_data <- lapply(lat_lon_data, function(x){x[ , `Lat, Long` := paste(Latitude, Longitude, sep = ', ')]}m)
mapply(function(x,y){fwrite(x, y)}, lat_lon_data, polling_path)
