library(data.table)
library(here)

setwd(here())
setwd('datasets/polling/Tarrant_County_TX')


dt_2024<- fread('Tarrant_County_TX_2024.csv')
dt_2025<- fread('Tarrant_County_TX_2025.csv')
dt_all <- merge(dt_2024, dt_2025, by = c('Location','Address'), all = TRUE)

dt_all[ , `Location type` := 'General_2024_2025'][ is.na(`Location type.x`), `Location type` := 'General_2025'
        ][ is.na(`Location type.y`), `Location type` := 'General_2024'
        ][ , `Location type.x`:= NULL][ , `Location type.y`:= NULL]


dt_all[ , `Lat, Long` := `Lat, Lon.x`][ is.na(`Lat, Long`), `Lat, Long` := `Lat, Lon.y`
        ][ , `Lat, Lon.x`:= NULL][ , `Lat, Lon.y`:= NULL]

fwrite(dt_all, 'Tarrant_County_TX_Locations_only.csv')
