library(data.table)
library(here)

setwd(here())

#load locations_only file. 
#this condtains 2 each of the following Location types:
#[1] "College Campus - Potential"   "Community Center - Potential"
#[3] "Elec Day Church - Potential"  "Elec Day School - Potential"
#[5] "Elec Day Other - Potential"   "EV_2022_2020"
#[7] "Fire Station - Potential"     "Library - Potential"
#[9] "Other - Potential"
testing_locations <- fread('datasets/polling/testing/testing_locations_only.csv')

#load relevant blocks and block groups
testing_2020 <- fread('datasets/polling/testing/testing_2020.csv')
testing_driving_2020 <- fread('datasets/polling/testing/testing_driving_2020.csv')
all.equal(testing_2020$id_orig, testing_driving_2020$id_orig)
#TRUE
all.equal(testing_2020[location_type== 'bg_centroid', ]$id_orig, testing_driving_2020[location_type== 'bg_centroid', ]$id_orig)
#TRUE
blocks <- unique(testing_2020$id_orig)
census_blocks <- paste0('1000000US', blocks)
block_groups <- unique(testing_2020[location_type== 'bg_centroid', ]$id_dest)
census_block_groups <- paste0('1500000US', block_groups)

#pull blocks and block_groups into census folders
read_census_data <- function(file_name, census_unit){
    header <- fread(file_name,  nrows = 2, header = FALSE)
    data <- fread(file_name, header = FALSE, skip = 2)
    testing_data <- data[V1 %in% census_unit, ]
    testing_data_with_header <- rbind(header, testing_data)
    return(testing_data_with_header)
}



Gwinnett_P3 <-read_census_data('datasets/census/redistricting/Gwinnett_County_GA/DECENNIALPL2020.P3-Data.csv', census_blocks)
Gwinnett_P4 <- read_census_data('datasets/census/redistricting/Gwinnett_County_GA/DECENNIALPL2020.P4-Data.csv', census_blocks)
Gwinnett_P3_bg <- read_census_data('datasets/census/redistricting/Gwinnett_County_GA/block group demographics/DECENNIALPL2020.P3-Data.csv', census_block_groups)
Gwinnett_P4_bg <- read_census_data('datasets/census/redistricting/Gwinnett_County_GA/block group demographics/DECENNIALPL2020.P4-Data.csv', census_block_groups)

foo <- fread('datasets/census/redistricting/Gwinnett_County_GA/block group demographics/DECENNIALPL2020.P3-Data.csv')

