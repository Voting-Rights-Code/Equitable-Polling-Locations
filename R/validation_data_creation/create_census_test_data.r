library(data.table)
library(here)
library(sf)

setwd(here())

#load locations_only file. 
#this condtains 2 each of the following Location types:
#[1] "College Campus - Potential"   "Community Center - Potential"
#[3] "Elec Day Church - Potential"  "Elec Day School - Potential"
#[5] "Elec Day Other - Potential"   "EV_2022_2020"
#[7] "Fire Station - Potential"     "Library - Potential"
#[9] "Other - Potential"
testing_locations <- fread('datasets/polling/testing/testing_potential_locations.csv')

#load relevant blocks and block groups
testing_2020 <- fread('datasets/polling/testing/testing_distances_2020.csv')
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

#redistricting P3 data
testing_P3 <-read_census_data('datasets/census/redistricting/Gwinnett_County_GA/DECENNIALPL2020.P3-Data.csv', census_blocks)
testing_P4 <- read_census_data('datasets/census/redistricting/Gwinnett_County_GA/DECENNIALPL2020.P4-Data.csv', census_blocks)
testing_P3_bg <- read_census_data('datasets/census/redistricting/Gwinnett_County_GA/block group demographics/DECENNIALPL2020.P3-Data.csv', census_block_groups)
testing_P4_bg <- read_census_data('datasets/census/redistricting/Gwinnett_County_GA/block group demographics/DECENNIALPL2020.P4-Data.csv', census_block_groups)
browser()
fwrite(testing_P3, 'datasets/census/redistricting/testing/DECENNIALPL2020.P3-Data.csv', col.names = FALSE)
fwrite(testing_P4, 'datasets/census/redistricting/testing/DECENNIALPL2020.P4-Data.csv', col.names = FALSE)
fwrite(testing_P3_bg, 'datasets/census/redistricting/testing/block group demographics/DECENNIALPL2020.P3-Data.csv', col.names = FALSE)
fwrite(testing_P4_bg, 'datasets/census/redistricting/testing/block group demographics/DECENNIALPL2020.P4-Data.csv', col.names = FALSE)

#tiger data
tiger_bg <- read_sf('datasets/census/tiger/Gwinnett_County_GA/tl_2020_13135_bg20.shp')
tiger_block <- read_sf('datasets/census/tiger/Gwinnett_County_GA/tl_2020_13135_tabblock20.shp')

testing_tiger_bg <- tiger_bg[tiger_bg$GEOID20 %in% block_groups, ]
testing_tiger_block <- tiger_block[tiger_block$GEOID20 %in% as.character(blocks), ]

st_write(testing_tiger_bg, 'datasets/census/tiger/testing/tl_2020_13135_bg20.shp')
st_write(testing_tiger_block, 'datasets/census/tiger/testing/tl_2020_13135_tabblock20.shp')

#CVAP data
Gwinnett_CVAP <- fread('datasets/census/CVAP/Gwinnett_County_GA/CVAP_2020-Data.csv')
testing_ACS <- Gwinnett_CVAP[GEOID20 %in% as.character(blocks) , ]
fwrite(testing_ACS, 'datasets/census/CVAP/testing/CVAP_2020-Data.csv')

#RDH projected VAP data
Gwinnett_projected_vap <- fread('datasets/census/RDH_projected_vap/Gwinnett_County_GA/ga_vap_proj_2026_2035_b.csv')
testing_projected_vap <- Gwinnett_projected_vap[GEOID %in% blocks, ]
fwrite(testing_projected_vap, 'datasets/census/RDH_projected_vap/testing/testing_vap_proj_2026_2035_b.csv')