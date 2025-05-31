library(data.table)
library(here)

#######
#Change directory
#######
setwd(here())

#######
#Read in data
#######

sample<- fread('datasets/polling/testing/testing_2020.csv')

#######
#Calculate alpha
#######
sample_alpha <- sample[dest_type == 'polling', .(distance_m = min(distance_m), population = unique(population)), by = id_orig]
sample_alpha[ , distance_sq :=distance_m * distance_m] 
alpha = sum(sample_alpha$population * sample_alpha$distance_m)/ sum(sample_alpha$population * sample_alpha$distance_sq)

#######
#Calculate kp_factors (for expanded)
#######

sample_expanded <- sample[!(location_type %in% c('bg_centroid', "Elec Day School - Potential")), ]
sample_expanded<- sample_expanded[ , kp_factor :=exp(2 * alpha * distance_m)]
test_kp_factor <- sample_expanded[ , .(id_orig, id_dest, kp_factor)]
fwrite(test_kp_factor, 'python/tests/test_kp_factor.csv')


