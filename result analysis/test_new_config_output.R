library(data.table)

#######
#Change directory
#######
setwd('~')
setwd('../../Voting Rights Code/Equitable-Polling-Locations')

######
#Read in results
######
old_result <- fread('Gwinnett_GA_results/Gwinnett_GA_configs.Gwinnett_config_expanded_11_result.csv')
old_result[ , V1:=NULL]
new_result <- fread('Gwinnett_GA_results/expanded_11_for_comparison/Gwinnett_GA_configs.Gwinnett_config_expanded_11_result.csv')
new_result[ , V1:=NULL]

#outer join by pairing
all_results <-merge(old_result, new_result, by = c('id_orig', 'id_dest'), 
					all = T)

#find duplicates by origin
different_matches <- all_results[ , .(number_matched = .N), by = id_orig
			][number_matched > 1, ]

#inner join to get the mismatched pairs
mismatches <- merge(all_results[, .(id_orig, id_dest)], different_matches, by = c('id_orig'))

old_edes <- fread('Gwinnett_GA_results/Gwinnett_GA_configs.Gwinnett_config_expanded_11_edes.csv')
new_edes <- fread('Gwinnett_GA_results/expanded_11_for_comparison/Gwinnett_GA_configs.Gwinnett_config_expanded_11_edes.csv')

merged_edes<-merge(old_edes, new_edes, by = c('demographic'))[ , y_ede_ratio := y_EDE.x/y_EDE.y]