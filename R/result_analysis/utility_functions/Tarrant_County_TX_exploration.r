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
latine_white_interaction_lpm_2025 <- lm(dropped_2025 ~ hispanic + white + (hispanic):(white), dt_pop_polls)
interact_plot(latine_white_interaction_lpm_2025, hispanic, white)+ ylim(0, 1)

latine_white_interaction_lpm_optimal <- lm(dropped_optimal ~ hispanic + white + (hispanic):(white), dt_pop_polls)
interact_plot(latine_white_interaction_lpm_optimal, hispanic, white)+ ylim(0, 1)

latine_white_interaction_logit_2025 <- glm(dropped_2025 ~ hispanic + white + (hispanic):(white), dt_pop_polls, family = binomial(link = "logit"))
interact_plot(latine_white_interaction_logit_2025, hispanic, white) + ylim(0, 1)

latine_white_interaction_logit_optimal <- glm(dropped_optimal ~ hispanic + white + (hispanic):(white), dt_pop_polls,  family = binomial(link = "logit"))
interact_plot(latine_white_interaction_logit_optimal, hispanic, white) + ylim(0, 1)

latine_white_logit_nointeract_2025 <- glm(dropped_2025 ~ hispanic + white, dt_pop_polls, family = binomial(link = "logit"))
interact_plot(latine_white_logit_nointeract_2025, hispanic, white) + ylim(0,1)

latine_white_logit_nointeract_optimal <- glm(dropped_optimal ~ hispanic + white, dt_pop_polls, family = binomial(link = "logit"))
interact_plot(latine_white_logit_nointeract_optimal, hispanic, white)+ ylim(0,1)

#caluclate odds ratios or probabilities
mean_hispanic <- mean(dt_pop_polls$hispanic)
mean_white <- mean(dt_pop_polls$white)
mean_whinteract <- mean(dt_pop_polls$hispanic*dt_pop_polls$white)

sd_hispanic <- sd(dt_pop_polls$hispanic)
sd_white <- sd(dt_pop_polls$white)
sd_whinteract <- sd(dt_pop_polls$hispanic*dt_pop_polls$white)


lpm_2025_hispanic_mean_white = latine_white_interaction_lpm_2025$coef['hispanic'] + latine_white_interaction_lpm_2025$coef['hispanic:white']*mean_white

lpm_optimal_hispanic_mean_white = latine_white_interaction_lpm_optimal$coef['hispanic'] + latine_white_interaction_lpm_optimal$coef['hispanic:white']*mean_white

lpm_2025_hispanic_SDpos_white = latine_white_interaction_lpm_2025$coef['hispanic'] + latine_white_interaction_lpm_2025$coef['hispanic:white']*(mean_white+ sd_white)

lpm_optimal_hispanic_SDpos_white = latine_white_interaction_lpm_optimal$coef['hispanic'] + latine_white_interaction_lpm_optimal$coef['hispanic:white']*(mean_white+ sd_white)

lpm_2025_hispanic_SDneg_white = latine_white_interaction_lpm_2025$coef['hispanic'] + latine_white_interaction_lpm_2025$coef['hispanic:white']*(mean_white- sd_white)

lpm_optimal_hispanic_SDneg_white = latine_white_interaction_lpm_optimal$coef['hispanic'] + latine_white_interaction_lpm_optimal$coef['hispanic:white']*(mean_white- sd_white)

#vectors of linear probabilities
c(lpm_2025_hispanic_SDneg_white, lpm_2025_hispanic_mean_white, lpm_2025_hispanic_SDpos_white)*1000
c(lpm_optimal_hispanic_SDneg_white, lpm_optimal_hispanic_mean_white, lpm_optimal_hispanic_SDpos_white)*1000


logit_2025_hispanic_mean_white = latine_white_interaction_logit_2025$coef['hispanic'] + latine_white_interaction_logit_2025$coef['hispanic:white']*mean_white

logit_optimal_hispanic_mean_white = latine_white_interaction_logit_optimal$coef['hispanic'] + latine_white_interaction_logit_optimal$coef['hispanic:white']*mean_white

logit_2025_hispanic_SDpos_white = latine_white_interaction_logit_2025$coef['hispanic'] + latine_white_interaction_logit_2025$coef['hispanic:white']*(mean_white+ sd_white)

logit_optimal_hispanic_SDpos_white = latine_white_interaction_logit_optimal$coef['hispanic'] + latine_white_interaction_logit_optimal$coef['hispanic:white']*(mean_white+ sd_white)

logit_2025_hispanic_SDneg_white = latine_white_interaction_logit_2025$coef['hispanic'] + latine_white_interaction_logit_2025$coef['hispanic:white']*(mean_white- sd_white)

logit_optimal_hispanic_SDneg_white = latine_white_interaction_logit_optimal$coef['hispanic'] + latine_white_interaction_logit_optimal$coef['hispanic:white']*(mean_white- sd_white)

#vectors of odds ratios
exp(c(logit_2025_hispanic_SDneg_white, logit_2025_hispanic_mean_white, logit_2025_hispanic_SDpos_white)*1000)
exp(c(logit_optimal_hispanic_SDneg_white, logit_optimal_hispanic_mean_white, logit_optimal_hispanic_SDpos_white)*1000)




#dt_all <- merge(dt_2024, dt_2025, all.x = TRUE, by = c('id_dest', 'demographic', 'source'))

#dt_all[, dropped := FALSE][is.na(avg_dist.y) , dropped := TRUE]

dropped_precincts <-  dt_2024[ , dropped_2025 := TRUE][id_dest %in% dt_2025$id_dest, dropped_2025 := FALSE]
#dropped_precincts <-  dt_2024[ , dropped_optimal := TRUE][id_dest %in% dt_optimal$id_dest, dropped_optimal := FALSE]


latine <- dropped_precincts[demographic == 'hispanic', ]
white <- dropped_precincts[demographic == 'white', ]
population <- dropped_precincts[demographic == 'population', ]

latine_2025<- glm(dropped_2025 ~ demo_pop, family = binomial, latine)
white_2025<- glm(dropped_2025 ~ demo_pop, family = binomial, white)
population_2025<- glm(dropped_2025 ~ demo_pop, family = binomial, population)

#latine_optimal <- glm(dropped_optimal ~ demo_pop, family = binomial, latine)
#white_optimal <- glm(dropped_optimal ~ demo_pop, family = binomial, white)
#population_optimal <-glm(dropped_optimal ~ demo_pop, family = binomial, population)



ggplot(latine, aes(x= demo_pop, y = dropped_2025)) + geom_point()
ggplot(latine, aes(x= demo_pop, y = dropped_optimal)) + geom_point()

##Daniel Exploration Below here
latine_white_comparison <- merge(latine, white, by="id_dest") 
latine_white_interaction_lpm <- lm(dropped_2025.x ~ demo_pop.x + demo_pop.y + (demo_pop.x):(demo_pop.y), latine_white_comparison)
interact_plot(latine_white_interaction_lpm, demo_pop.x,demo_pop.y)