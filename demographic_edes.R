library(data.table)
library(ggplot2)
library(stringr)

#######
#Change directory
#######
setwd('../../Equitable-Polling-Locations')

######
#Read in results
######
ede_files <- list.files('Gwinnett_GA_results/', pattern = 'edes')
precinct_files <- list.files('Gwinnett_GA_results/', pattern = 'precinct_distances')
config_names <- lapply(ede_files, function(x){gsub(".*Gwinnett_config_\\s*|_edes.*", "", x)})


ede_file_path <- paste0('Gwinnett_GA_results/', ede_files) 
precinct_file_path <- paste0('Gwinnett_GA_results/', precinct_files) 

ede_df_list <-lapply(ede_file_path, fread)
precinct_df_list <-lapply(precinct_file_path, fread)

names(ede_df_list) <- config_names
names(precinct_df_list) <- config_names
#######
#clean data
#######
num_polls <- lapply(precinct_df_list, nrow)
mapply(function(x, y){x[ , num_polls:=y/6]}, ede_df_list, num_polls)

expanded <- ede_df_list[grepl('expanded', names(ede_df_list))]
original <- ede_df_list[grepl('original', names(ede_df_list))]
full <- ede_df_list[grepl('full', names(ede_df_list))]

all_expanded <- do.call(rbind, expanded)
all_original <- do.call(rbind, original)
all_full <- do.call(rbind, full)

all_expanded[ , level := 'expanded']
all_original[ , level := 'original']
all_full[ , level := 'full']

#######
#plot edes
#######

ggplot(all_expanded, aes(x = num_polls, y = y_EDE, 
		group = demographic, color = demographic, shape = demographic)) +
		geom_line()+ geom_point() +
	geom_point(data = all_original, aes(x = num_polls, y = y_EDE, 
		group = demographic, color = demographic, shape = demographic))

ggsave('demographic_edes_with_originals.png')

