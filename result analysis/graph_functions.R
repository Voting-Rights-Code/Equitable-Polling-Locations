library(data.table)
library(ggplot2)
library(stringr)
library(here)


#######
#Check that location and folders valid
#######
check_location_valid <- function(location, config_folder){
	#raise error if config folder does not start with location
	if (!grepl(paste0('^', location), config_folder)){
    stop('Given config folder does not start with the given location')
}
}

check_config_folder_valid <- function(config_folder){
	#raise error if config folder not a directory
	if (!(config_folder %in% list.files())){
    	stop('Config folder does not exist')
}
}

######
#Functions to read in results
######

combine_results <-function(config_folder, result_type){
	#combine all the data of a certain type 
	#(ede, precinct, residence, result)
	#from indicated config_folder and output a df
	#config_folder, result_type: string
	#returns: data frame

	#select which results we want
	result_folder <-paste(location, 'results/', sep = '_')
	files <- list.files(result_folder)
	files <- files[grepl(config_folder, files) &grepl(result_type, files)]
	file_path <- paste0(result_folder, files)
	df_list <- lapply(file_path, fread)

	#name the data from the file names
	config_names_long <- lapply(files, function(x){gsub(paste0('.*', county_config_,"\\s*|.csv*"), "", x)})	
	config_names <- lapply(config_names_long, function(x){gsub(paste0('_',result_type), "", x)})
	file_path <- paste0(result_folder, files)
	df_list <- lapply(file_path, fread)
	names(df_list) <- config_names

	#label with names and levels
	mapply(function(x, y){x[ , descriptor:= y]}, df_list, names(df_list))
	
	#Change id_dest and id_orig to strings as needed
	if ('id_dest' %in% names(df_list[[1]])){
		sapply(df_list, function(x){x[ , id_dest:= as.character(id_dest)]})}
	if ('id_orig' %in% names(df_list[[1]])){
		sapply(df_list, function(x){x[ , id_orig:= as.character(id_orig)]})}
	
	#combine into one df
	big_df <- do.call(rbind, df_list)

	return(big_df)
}

read_result_data<- function(config_folder){
	#read in and format all the results data assocaited to a 
	#given config folder.
	#config_folder: string
	#returns: list(ede_df, precinct_df, residence_df, result_df)
	
	#combine all files with a descriptor column attached
	ede_df<- combine_results(config_folder, 'edes')
	precinct_df<- combine_results(config_folder, 'precinct_distances')
	residence_df<- combine_results(config_folder, 'residence_distances')
	result_df<- combine_results(config_folder, 'result')

	#label descriptors with polls and residences
	num_polls <- precinct_df[ , .(num_polls = .N/6), by = descriptor]
	num_residences <- residence_df[ , .(num_residences = .N/6), by = descriptor]
	nums_to_join <- merge(num_polls, num_residences, all = T)

	ede_df <- merge(ede_df,nums_to_join, all.x = T)
	precinct_df <- merge(precinct_df,nums_to_join, all.x = T)
	residence_df <- merge(residence_df,nums_to_join, all.x = T)
	result_df <- merge(result_df,nums_to_join, all.x = T)

	return(list(ede_df, precinct_df, residence_df, result_df))
}

check_run_validity <- function(config, orig){
	#Input: A pair of result_dfs (each corresponding to a config folder) that should have the same number of matched residences
	#Check that they do both within and across data frames
	#Else return an error
	combined_df <- rbind(config, orig)
	unique_num_residences <- length(unique(combined_df$num_residences))

	max_num_residences = max(combined_df$num_residences)
	bad_runs <- combined_df[ , .(num_polls = mean(num_polls)), by = c('descriptor', 'num_residences')][num_residences < max_num_residences, ]
	
	#flag if an "original" run has too few residences
	if (any(grepl('original', bad_runs$descriptor))){
		stop('One of the original runs does not match enough residences. Rerun')
	} else if (nrow(bad_runs)>0){#if there is a bad run, remove it
		cat('The following runs do not have enough residences: ', bad_runs$descriptor)
		warning('Removing the data from these runs')
	}
	return(bad_runs$descriptor)
}

#######
#functions to make plots
#######

plot_demographic_edes<-function(ede_df){
	ggplot(ede_df, aes(x = num_polls, y = y_EDE, 
		group = demographic, color = demographic, shape = demographic)) +
		geom_line()+ geom_point()+ 
		labs(x = 'Number of polls', y = 'Equity weighted distance (m)')
	ggsave('demographic_edes.png')
}

plot_original_optimized <- function(config_ede, orig_ede){	
	#makes two plots, one showing the y_ede differences between the actual positioning and an equivalent optimized run; the other doing the same but with average distances

	#select the relevant optimized runs
	orig_num_polls <- unique(orig_ede$num_polls)
	optimized_run_dfs <- config_ede[num_polls %in% orig_num_polls]
	orig_and_optimal <- rbind(orig_ede, optimized_run_dfs)
	descriptor_order <- unique(orig_and_optimal$descriptor)
	#plot with y_EDE
	ggplot(orig_and_optimal, aes(x = descriptor, y = y_EDE, 
		group = demographic, color = demographic, shape = demographic)) +
		geom_point(aes(x = factor(descriptor, level = descriptor_order), ), size = 9) +
		labs(x = 'Optimization run', y = 'Equity weighted distance (m)')
	ggsave('orig_and_optimal.png')
	#polot with avg_dist
	ggplot(orig_and_optimal, aes(x = descriptor, y = avg_dist, 
		group = demographic, color = demographic, shape = demographic)) +
		geom_point(aes(x = factor(descriptor, level = descriptor_order), size = 9)) +
		labs(x = 'Optimization run', y = 'Average distance (m)')
	ggsave('orig_and_optimal_avg.png')
}

plot_population_edes <- function(ede_df){	
	#plots just the y_edes for the population as a whole
	ggplot(ede_df[demographic == 'population', ], aes(x =  num_polls, y = y_EDE))+
		geom_line()+ geom_point()+
		labs(x = 'Number of polls', y = 'Equity weighted distance (m)')

	ggsave('population_edes.png')
}

plot_precinct_persistence <- function(precinct_df){
	#a plot showing which precincts are used for which number of polls
	ggplot(precinct_df[demographic == 'population',
		], aes(x = num_polls, y = id_dest)) +
		geom_point(aes(size = demo_pop)) + 
		labs(x = 'Number of polls', y = 'EV location')

	ggsave('expanded_precinct_persistence.png')

	#also makes a panel of graphs showing which demographics are assigned to each poll
	ggplot(precinct_df[demographic != 'population',
		], aes(x = num_polls, y = id_dest)) +
		geom_point(aes(size = demo_pop)) + 
		labs(x = 'Number of polls', y = 'EV location') + facet_wrap(~ demographic) +
		theme(legend.position = c(0.9, 0.2))

	ggsave('expanded_precinct_persistence_all.png')
}

plot_boxplots <- function(residence_df){
	#make boxplots of the average distances traveled and the y_edes at each run 
	res_pop <- residence_df[demographic == 'population',
		]
	#avg distance
	ggplot(res_pop, aes(x = num_polls, y = avg_dist, group = descriptor)) +
		stat_boxplot(geom = "errorbar")+
		geom_boxplot(outlier.shape = NA) + 
		scale_y_log10(limits = c(500,10500)) +
		labs(x = 'Number of polls', y = 'Average distance (m)')
	ggsave('avg_dist_distribution_boxplots.png')
	}

plot_orig_ideal_hist <- function(orig_residence_df, config_residence_df, ideal_num){
	#make histogram of the average distances traveled and the y_edes in the original and ideal situations 
	orig_residence_df <- orig_residence_df[demographic == 'population', ]
	ideal_residence_df <- config_residence_df[demographic == 'population', ][num_polls == ideal_num, ]
	res_pop_orig_and_ideal <- rbind( ideal_residence_df, orig_residence_df)
	location_ <- paste0(location, '_')
	config_label <- sub(location_, '', config_folder)
	descriptor_order <- unique(res_pop_orig_and_ideal$descriptor)

	#avg_distance
	ggplot(res_pop_orig_and_ideal, aes(x = avg_dist, fill = descriptor)) + 
		geom_histogram(aes(weight = demo_pop), position = "dodge", alpha = 0.8)+
		labs(x = 'Average distance traveled to poll (m)', y = 'Number of people') +
		scale_fill_manual(values=c("red", "blue", "green"), name = "Optimization run ", 
		labels = descriptor_order)
		ggsave('avg_dist_distribution_hist.png')

}




compare_configs<- function(config_ede, config_folder2){
	#takes a config folder name, processes the files in it, and compares its mean y_ede to the current one under consideration

	#Check that folder is valid
	check_location_valid(location, config_folder2)
	check_config_folder_valid(config_folder2)

	#Read in data
	config2_df_list <- read_result_data(config_folder2)
	config2_ede <- config2_df_list[1]

	#label configs
	location_ <- paste0(location, '_')
	config1_label <- sub(location_, '', config_folder)
	config2_label <- sub(location_, '', config2_folder) 
	config_ede <- config_ede[ , run := config1_label]
	config2_ede <- config2_ede[ , run := config2_label]
	
	#combine and select the population scores only
	dt <-rbind(config_ede, config2_ede)
	dt <- dt[demographic == 'population', ]
	ggplot(dt, aes(x =  num_polls, y = y_EDE, group = run, 
			color = run))+
		geom_line()+ geom_point()+
		labs(x = 'Number of polls', y = 'Equity weighted distance (m)')

	ggsave(paste0(config1_label, '_vs_', config2_label, '.png'))
}

