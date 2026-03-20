library(data.table)
library(interactions)
library(ggplot2)
library(here)

setwd(here())


#read in 2024, and 2025 historical precinct data, as well as the optimal assignments
dt_2024 <- fread('datasets/results/Tarrant_County_TX_results/Tarrant_County_TX_original_configs_capacity_2.Tarrant_County_TX_year_2024_precinct_distances.csv')

dt_2025 <- fread('datasets/results/Tarrant_County_TX_results/Tarrant_County_TX_original_configs_capacity_2.Tarrant_County_TX_year_2025_precinct_distances.csv')

dt_optimal <- fread('datasets/results/Tarrant_County_TX_results/Tarrant_County_TX_fair_capacity_2.Tarrant_County_TX_precincts_open_215_precinct_distances.csv')

#separate out demographic numbers into columns
#Note, this loses the distance data
dt_2024_pop <- dcast(dt_2024, id_dest ~ demographic, value.var = 'demo_pop' )

#add in flags for when a polling location is dropped
polls_2025 = unique(dt_2025$id_dest)
polls_optimal  = unique(dt_optimal$id_dest)

dt_pop_polls <- dt_2024_pop[ , dropped_2025 := TRUE
                ][id_dest %in% polls_2025, dropped_2025 := FALSE
                ][ , dropped_optimal := TRUE][id_dest %in% polls_optimal, dropped_optimal := FALSE]

#run models
#Linear Probability Model intacting Latine and White
latine_white_interaction_lpm_2025 <- lm(dropped_2025 ~ hispanic + white + (hispanic):(white), dt_pop_polls)
interact_plot(latine_white_interaction_lpm_2025, hispanic, white, 
  main.title ="Actual Effect of Latine Population on Probability of Poll Closure (LPM)", y.label = "Probability of Poll Closure", x.label = "Latine Population",
  legend.main = "White Population") + ylim(0, 1)

latine_white_interaction_lpm_optimal <- lm(dropped_optimal ~ hispanic + white + (hispanic):(white), dt_pop_polls)
interact_plot(latine_white_interaction_lpm_optimal, hispanic, white,
  main.title ="Optimal Race-Blind Effect of Latine Population on Probability of Poll Closure (LPM)", y.label = "Probability of Poll Closure", x.label = "Latine Population",
  legend.main = "White Population") + ylim(0, 1)

#Logit interaction Latine and white

latine_white_interaction_logit_2025 <- glm(dropped_2025 ~ hispanic + white + (hispanic):(white), dt_pop_polls, family = binomial(link = "logit"))
interact_plot(latine_white_interaction_logit_2025, hispanic, white,
  main.title ="Actual Effect of Latine Population on Probability of Poll Closure (Logistic)", y.label = "Probability of Poll Closure", x.label = "Latine Population",
  legend.main = "White Population") + ylim(0, 1)

latine_white_interaction_logit_optimal <- glm(dropped_optimal ~ hispanic + white + (hispanic):(white), dt_pop_polls,  family = binomial(link = "logit"))
interact_plot(latine_white_interaction_logit_optimal, hispanic, white,
  legend.main = "White Population") + ylim(0, 1)


