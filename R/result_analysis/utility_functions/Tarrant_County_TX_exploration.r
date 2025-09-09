library(data.table)
library(ggplot2)
library(here)

setwd(here())

dt_2024 <- fread('datasets/results/Tarrant_County_TX_results/Tarrant_County_TX_original_configs_capacity_2.Tarrant_County_TX_year_2024_precinct_distances.csv')

dt_2025 <- fread('datasets/results/Tarrant_County_TX_results/Tarrant_County_TX_original_configs_capacity_2.Tarrant_County_TX_year_2025_precinct_distances.csv')

dt_optimal <- fread('datasets/results/Tarrant_County_TX_results/Tarrant_County_TX_fair_capacity_2.Tarrant_County_TX_precincts_open_215_precinct_distances.csv')

#dt_all <- merge(dt_2024, dt_2025, all.x = TRUE, by = c('id_dest', 'demographic', 'demo_pop', 'source'))

#dt_all[, dropped := FALSE][is.na(avg_dist.y) , dropped := TRUE]

dropped_precincts <-  dt_2024[ , dropped_2025 := TRUE][id_dest %in% dt_2025$id_dest, dropped_2025 := FALSE]
dropped_precincts <-  dt_2024[ , dropped_optimal := TRUE][id_dest %in% dt_optimal$id_dest, dropped_optimal := FALSE]


latine <- dropped_precincts[demographic == 'hispanic', ]
white <- dropped_precincts[demographic == 'white', ]
population <- dropped_precincts[demographic == 'population', ]

latine_2025<- glm(dropped_2025 ~ demo_pop, family = binomial, latine)
white_2025<- glm(dropped_2025 ~ demo_pop, family = binomial, white)
population_2025<- glm(dropped_2025 ~ demo_pop, family = binomial, population)

latine_optimal <- glm(dropped_optimal ~ demo_pop, family = binomial, latine)
white_optimal <- glm(dropped_optimal ~ demo_pop, family = binomial, white)
population_optimal <-glm(dropped_optimal ~ demo_pop, family = binomial, population)



ggplot(latine, aes(x= demo_pop, y = dropped_2025)) + geom_point()
ggplot(latine, aes(x= demo_pop, y = dropped_optimal)) + geom_point()
