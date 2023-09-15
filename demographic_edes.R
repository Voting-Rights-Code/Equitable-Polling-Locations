library(data.table)
library(ggplot2)

#######
#Change directory
#######
setwd('../../Equitable-Polling-Locations')

######
#Read in results
######
result_files <- list.files('Gwinnett_GA_result/', pattern = 'edes')
result_file_path <- paste0('Gwinnett_GA_result/', result_files) 
result_df_list <-lapply(result_file_path, fread)

#######
#clean data
#######
num_polls_added <- lapply(seq_along(result_df_list), function(i){result_df_list[[i]][
									 , num_polls := i+10]})
all_data <- do.call(rbind, num_polls_added)
all_data <- all_data[, .SD, .SDcols = unique(names(all_data))]
#######
#plot edes
#######

ggplot(all_data, aes(x = num_polls, y = y_EDE, 
		group = demographic, color = demographic, shape = demographic)) +
		geom_line()+ geom_point()

ggsave('demographic_edes.pdf')

