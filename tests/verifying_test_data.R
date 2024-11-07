library(data.table)

#######
#Change directory
#######
setwd('~')
setwd('../../Voting Rights Code/Equitable-Polling-Locations')

#######
#Read in data
#######

sample<- fread('datasets/polling/testing/testing.csv')

#######
#Calculate alpha
#######
sample_alpha <- sample[dest_type == 'polling', .(distance_m = min(distance_m), population = unique(population)), by = id_orig]
sample_alpha[ , distance_sq :=distance_m * distance_m] 
alpha = sum(sample_alpha$population * sample_alpha$distance_m)/ sum(sample_alpha$population * sample_alpha$distance_sq)

#######
#Calculate kp_factors (for expanded)
#######

sample_expanded <- sample[!(location_type %in% c('bg_centroid', "Election Day Loc - Potential")), ]
sample_expanded<- sample_expanded[ , kp_factor :=exp(2 * alpha * distance_m)]
test_kp_factor <- sample_expanded[ , .(id_orig, id_dest, kp_factor)]
fwrite(test_kp_factor, 'tests/test_kp_factor.csv')


dt_old_2020<- fread("Gwinnett_County_GA_results/Gwinnett_County_GA_original_old/Gwinnett_County_GA_configs.Gwinnett_config_original_2020_result.csv")
dt_new_2020<- fread("Gwinnett_County_GA_results/Gwinnett_County_GA_configs.Gwinnett_config_original_2020_result.csv")
all.equal(dt_old_2020, dt_new_2020)

