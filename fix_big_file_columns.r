library(data.table)
library(here)

wrong_county_list = c("Gwinnett_GA", "DeKalb_County_GA", "Cobb_GA", "Berkeley_SC", "Lexington_SC", "Greenville_SC", "Richland_SC", "York_SC")
right_county_list = c("Gwinnett_County_GA", "DeKalb_County_GA", "Cobb_County_GA", "Berkeley_County_SC", "Lexington_County_SC", "Greenville_County_SC", "Richland_County_SC", "York_County_SC")


wrong_city_list = c("Norfolk_City_VA", "Virginia_Beach_City_VA" )
right_city_list = c("Norfolk_city_VA", "Virginia_Beach_city_VA" )

change_dt <- function(right){
    file_name <- paste0('datasets/polling/', right, '/', right, '.csv')
    dt_big <- fread(file_name)
    dt_big[ , county:= right]
    fwrite(dt_big, file_name)    
}

#sapply(right_county_list, change_dt)
#sapply(right_city_list, change_dt)

change_dt(DeKalb_County_GA)
