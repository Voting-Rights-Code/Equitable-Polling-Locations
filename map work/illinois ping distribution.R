library(data.table)
library(ggplot2)
library(lubridate)
library(mapview)
library(sf)
library(cartogram)
library(broom)


#########
#change directory for map data
#this is data from Tiger, 2020
#########

setwd("~")
setwd("../../Equitable-Polling-Locations/datasets/census/tiger/Gwinnett_GA/") 

#Read in block and block group shape files
map_bg <- st_read("tl_2020_13135_bg20.shp")
maps_bg_dt<- as.data.table(map_bg)
maps_bg_dt <- maps_bg_dt[ , AREA20 := ALAND20 + AWATER20
				][ , .(GEOID20, AREA20, geometry)]


maps_bg_sf<-st_as_sf(maps_bg_dt)

ggplot() +
  geom_sf(data = maps_bg_sf)

#########
#get bg population
#########
setwd("~")
setwd("../../Equitable-Polling-Locations/datasets/census/redistricting/Gwinnett_GA") 

demo_dt <- fread("block group demographics/DECENNIALPL2020.P4-Data.csv", skip = 1, header = T)

#clean up data
demo_dt<-demo_dt[,1:3]
demo_dt[, Geography := gsub("1500000US", '', Geography)]
setnames(demo_dt, " !!Total:", "Population")
#########
#combine data
#########

bg_area_pop <- merge(demo_dt, maps_bg_dt, by.x = 'Geography', by.y = 'GEOID20')

pop_sf <- st_as_sf(bg_area_pop)
#########
#make maps
#########

pop_merc <- st_transform(pop_sf, 3857)

ggplot() +  geom_sf(data = pop_merc)

Gwinnett_cartogram <- cartogram_cont(pop_merc, "Population")

ggplot() +  geom_sf(data = Gwinnett_cartogram)



