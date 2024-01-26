library(data.table)
library(ggplot2)
library(stringr)

#######
#Change directory
#######
setwd('~')
setwd('../../Equitable-Polling-Locations')

######
#Read in results
######
#local run
process_results <-function(result_type){
	#Read and name data of the correct type
	files <- list.files('Gwinnett_GA_results/', pattern = result_type)
	config_names_long <- lapply(files, function(x){gsub(".*Gwinnett_config_\\s*|.csv*", "", x)})	
	config_names <- lapply(config_names_long, function(x){gsub(paste0('_',result_type), "", x)})
	file_path <- paste0('Gwinnett_GA_results/', files)
	df_list <- lapply(file_path, fread)
	names(df_list) <- config_names

	#label with names and levels
	#num_polls <- c(rep(11:30, 2), 50, 9, 11) #note, this is hard coded and brittle
	#mapply(function(x, y){x[ , num_polls:=y/6]}, df_list, num_polls)
	mapply(function(x, y){x[ , descriptor:= y]}, df_list, names(df_list))
	
	if ('id_dest' %in% names(df_list[[1]])){
		sapply(df_list, function(x){x[ , id_dest:= as.character(id_dest)]})}
	if ('id_orig' %in% names(df_list[[1]])){
		sapply(df_list, function(x){x[ , id_orig:= as.character(id_orig)]})}
	
	big_df <- do.call(rbind, df_list)
	
	#add level column
	big_df <- big_df[grepl('expanded', descriptor), level:='expanded'
		][grepl('full', descriptor), level:='full'
		][grepl('original', descriptor), level:='original'
		]
	return(big_df)
}

#combine all files with a descriptor column attached
ede_df<- process_results('edes')
precinct_df<- process_results('precinct_distances')
residence_df<- process_results('residence_distances')
result_df<- process_results('result')

#label descriptors with polls and residences
num_polls <- precinct_df[ , .(num_polls = .N/6), by = descriptor]
num_residences <- residence_df[ , .(num_residences = .N/6), by = descriptor]
nums_to_join <- merge(num_polls, num_residences, all = T)

ede_df <- merge(ede_df,nums_to_join, all.x = T)
precinct_df <- merge(precinct_df,nums_to_join, all.x = T)
residence_df <- merge(residence_df,nums_to_join, all.x = T)
result_df <- merge(result_df,nums_to_join, all.x = T)


#######
#plot edes
#######
setwd('result analysis/')

ggplot(ede_df[level =='expanded', ]
	, aes(x = num_polls, y = y_EDE, 
		group = demographic, color = demographic, shape = demographic)) +
		geom_line()+ geom_point() +
	geom_point(data = ede_df[grepl('original', descriptor), ], aes(x = num_polls, y = y_EDE, 
		group = demographic, color = demographic, shape = demographic)) + 
	labs(x = 'Number of polls', y = 'Equity weighted distance (m)')

ggsave('demographic_edes_with_originals.png')

ggplot(ede_df[level =='expanded', ], aes(x = num_polls, y = y_EDE, 
		group = demographic, color = demographic, shape = demographic)) +
		geom_line()+ geom_point()+ 
		labs(x = 'Number of polls', y = 'Equity weighted distance (m)')

ggsave('demographic_edes.png')

at_most_11 <- rbind(ede_df[level =='original', ], ede_df[descriptor == 'expanded_11', ])
level_order <- c('expanded_11', 'original_2022', 'original_2020')
ggplot(at_most_11, aes(x = descriptor, y = y_EDE, 
		group = demographic, color = demographic, shape = demographic)) +
		geom_point(aes(x = factor(descriptor, level = level_order))) +
		labs(x = 'Optimization run', y = 'Equity weighted distance (m)')

ggsave('at_most_11.png')


good_runs_pops <- ede_df[num_polls != 50, 
			][!(descriptor %in% c('full_27', 'full_29')), 
			][demographic == 'population', ] 

ggplot(good_runs_pops[level %in% c('expanded', 'full'), ], aes(x =  num_polls, y = y_EDE, group = level, 
			color = level))+
		geom_line()+ geom_point()+
		labs(x = 'Number of polls', y = 'Equity weighted distance (m)')

ggsave('demographic_edes_expanded_full.png')

ggplot(precinct_df[demographic == 'population',
		][level == 'expanded', ], aes(x = num_polls, y = id_dest)) +
		geom_point(aes(size = demo_pop)) + 
		labs(x = 'Number of polls', y = 'EV location')

ggsave('expanded_precinct_persistence.png')

ggplot(precinct_df[demographic != 'population',
		][level == 'expanded', ], aes(x = num_polls, y = id_dest)) +
		geom_point(aes(size = demo_pop)) + 
		labs(x = 'Number of polls', y = 'EV location') + facet_wrap(~ demographic) +
		theme(legend.position = c(0.9, 0.2))

ggsave('expanded_precinct_persistence.png')

res_pop <- residence_df[demographic == 'population',
		][num_polls != 50, 
			][!(descriptor %in% c('full_27', 'full_29')), 
			]#[level %in% c('expanded', 'full')] 
ggplot(res_pop, aes(x = num_polls, y = avg_dist, group = descriptor)) +
	stat_boxplot(geom = "errorbar")+
	geom_boxplot(outlier.shape = NA, aes(fill = level)) + 
	scale_y_log10(limits = c(500,10500)) +
	labs(x = 'Number of polls', y = 'Average distance (m)')
ggsave('avg_dist_distribution_boxplots.png')

res_pop_orig_and_22 <- res_pop[descriptor %in% c('original_2020', 'original_2022', 'expanded_22')]
ggplot(res_pop_orig_and_22, aes(x = avg_dist, fill = descriptor)) + 
	#geom_density()	
	geom_histogram(position = "dodge", alpha = 0.8)+
	labs(x = 'Average distance traveled to poll (m)', y = 'Number of census blocks') +
	scale_fill_manual(values=c("red", "blue", "green"), name = "Optimization run ", 
		labels = c("22 Locations", "2020 locations", "2022 locations")) +
	
ggsave('avg_dist_distribution_hist.png')



res_aa <- residence_df[demographic == 'black'
		][descriptor %in% c('original_2020', 'original_2022', 'expanded_11', 'expanded_22')]
ggplot(res_aa, aes(x = avg_dist, color = descriptor)) + 
	#geom_density()	
	geom_histogram(position = "identity", alpha = 0.4)

#######
#make datasets for maps
#######

#dataset of all possible locations (has lat/lon)
potential_locations <- fread('datasets/polling/Gwinnett_GA/Gwinnett_GA.csv')
unique_locations <- potential_locations[, .(dest_lat = unique(dest_lat), dest_lon = unique(dest_lon)), by= id_dest, ]

#dataset of matched locations with only one entry for location
unique_precincts <- lapply(precinct_df_list, 
	function(x){x[demographic == 'population', ]})
unique_precincts$full_50 <- unique_precincts$full_50[ , id_dest:= as.character(id_dest)]

#merge
geotagged_precincts <- lapply(unique_precincts, function(X){unique_locations[X, on = 'id_dest']})

#write
setwd('datasets/polling/Gwinnett_GA/model_outputs_for_mapping')
map_file_names <- paste0(names(geotagged_precincts), '.csv')
mapply(function(x, y) {fwrite(x, y)}, 
	geotagged_precincts, map_file_names)