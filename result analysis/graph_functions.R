library(data.table)
library(ggplot2)
library(stringr)
library(here)
library(plotly)


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
#Two types to analysis: historical (see CLC work); placement (see FFA work)
######

#####Formatting notes:
	# Historical analysis
	   # One config file contains multiple locations or multiple years
 	   # (E.G. Engage_VA or CLC analysis)
	   # N.B. Year must be in the config file name for this to work, 
		 # it must be the ONLY numbers in the file name
	# Placement analysis
	   # One config file contains single location and either
	      # multiple optimized placement
	   # (E.g. FFA analysis)
	   # N.B. Number of polls must be in the config file name for this to work, 
		 # it must be the ONLY numbers in the file name

combine_results<- function(location, config_folder, result_type, analysis_type = 'placement'){
	#determined what type of analysis is to be done, and call the appropriate function
	#currently valid types: historical (see CLC work); placement (see FFA work)
	if (analysis_type == 'historical'){
		#select which results we want (potentially from a list of folders)
		result_folder_list <-sapply(location, function(x){paste(x, 'results/', sep = '_')})
		files <- lapply(result_folder_list, list.files)
		files <- sapply(location, function(x){files[[x]][grepl(config_folder, files[[x]]) &grepl(result_type, files[[x]])]})
		file_path <- mapply(function(folder, file){paste0(folder, file)}, result_folder_list, files)
		
		#pull the historical year from the file names
		years <-  gsub('.*?([0-9]+).*', '\\1', files)
		descriptor <- mapply(function(x,y){paste(x, y, sep='_')}, location, years)}
	else if (analysis_type == 'placement'){
		result_folder <-paste(location, 'results/', sep = '_')
		files <- list.files(result_folder)
		files <- files[grepl(config_folder, files) &grepl(result_type, files)]
		file_path <- paste0(result_folder, files)
		
		#pull number of polls data from the file names
		num_polls <-  gsub('.*?([0-9]+).*', '\\1', files)
		descriptor <- sapply(num_polls, function(x){paste('Optimized', num_polls, 'polls', sep='_')})}
	else{
		stop("Incorrect analysis_type provided. Analysis type must be historical or placement")}
	
	#read data
	df_list <- lapply(file_path, fread)

	#add appropriate descriptor
	mapply(function(x, y){x[ , descriptor:= y]}, df_list, descriptor)
	
	#Change id_dest and id_orig to strings as needed
	if ('id_dest' %in% names(df_list[[1]])){
		sapply(df_list, function(x){x[ , id_dest:= as.character(id_dest)]})}
	if ('id_orig' %in% names(df_list[[1]])){
		sapply(df_list, function(x){x[ , id_orig:= as.character(id_orig)]})}
	
	#combine into one df
	big_df <- do.call(rbind, df_list)

	return(big_df)
}


###################
# BEGIN REMOVE
###################
combine_results_multi_county_historical <- function(config_folder, result_type){
	#combine all the data of a certain type 
	#(ede, precinct, residence, result)
	#from indicated config_folder with potentially multiple locations
	#and year encoded in the name and output a df
	#config_folder, result_type: string
	#returns: data frame

	#select which results we want
	result_folder_list <-sapply(location, function(x){paste(x, 'results/', sep = '_')})
	files <- lapply(result_folder_list, list.files)
	files <- sapply(location, function(x){files[[x]][grepl(config_folder, files[[x]]) &grepl(result_type, files[[x]])]})
	file_path <- mapply(function(folder, file){paste0(folder, file)}, result_folder_list, files)
	df_list <- lapply(file_path, fread)

	#pull the historical year from the file names
	years <-  gsub('.*?([0-9]+).*', '\\1', files)
	descriptor <- mapply(function(x,y){paste(x, y, sep='_')}, location, years)
	
	#descriptor is county_name_year
	mapply(function(x, y){x[ , descriptor:= y]}, df_list, descriptor)
	
	#Change id_dest and id_orig to strings as needed
	if ('id_dest' %in% names(df_list[[1]])){
		sapply(df_list, function(x){x[ , id_dest:= as.character(id_dest)]})}
	if ('id_orig' %in% names(df_list[[1]])){
		sapply(df_list, function(x){x[ , id_orig:= as.character(id_orig)]})}
	
	#combine into one df
	big_df <- do.call(rbind, df_list)

	return(big_df)
}

##### Code for when there is only one location in the config folder,
	# config folder starts with that string (e.g. FFA analysis) ######
combine_results_placement <-function(config_folder, result_type){
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

	#label with names and levels
	config_names_long <- lapply(files, function(x){gsub(paste0('.*', county_config_,"\\s*|.csv*"), "", x)})	
	config_names <- lapply(config_names_long, function(x){gsub(paste0('_',result_type), "", x)})
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
###################
# END REMOVE
###################

read_result_data<- function(location, config_folder, analysis_type){
	#read in and format all the results data assocaited to a 
	#given config folder.
	#config_folder: string
	#analysis_type: string (historical, placement)
	#returns: list(ede_df, precinct_df, residence_df, result_df)
	
	#combine all files with a descriptor column attached
	ede_df<- combine_results(location, config_folder, 'edes', analysis_type)
	precinct_df<- combine_results(location, config_folder, 'precinct_distances', analysis_type)
	residence_df<- combine_results(location, config_folder, 'residence_distances', analysis_type)
	result_df<- combine_results(location, config_folder, 'result', analysis_type)

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

###################
# BEGIN REMOVE
# No longer needed due to bug fix
###################

check_run_validity <- function(combined_df){
	#Input: A pair of result_dfs (each corresponding to a config folder) that should have the same number of matched residences
	#Check that they do both within and across data frames
	#Else return an error
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

###################
# END REMOVE
###################

#######
#dictionary for labels
#######

demographic_legend_dict <- c(
	'asian' = 'Asian (not PI)', 
	'black' = 'African American', 
	'white' = 'White', 
	'hispanic' = 'Latine',
	'native' = 'First Nations',
	'population' = 'Total')

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

plot_election_edes <- function(config_folder, orig_ede, suffix = ''){	
	#makes two plots, one showing the y_ede differences between the actual positioning and an equivalent optimized run; the other doing the same but with average distances

	#set graph order
	descriptor_order <- unique(orig_ede$descriptor)

	#select y axis bounds
	all_y_values = c(c(orig_ede$avg_dist), c(orig_ede$y_EDE))
	y_min = min(all_y_values)
	y_max = max(all_y_values)

	#set point size
	#does data contain scaling data
	scale_bool = 'pct_demo_population' %in% names(orig_ede)
	
	#is this driving distance data
	if (grepl('driving', config_folder)){
		y_EDE_label = 'Equity weighted driving distance (m)'
		y_avg_label = 'Average driving distance (m)'
		title_str = "driving distance by demographic and optimization run"
	} else {
		y_EDE_label = 'Equity weighted distance (m)'
		y_avg_label = 'Average distance (m)'
		title_str = "distance by demographic and optimization run"
	}
	#plot with y_EDE
	y_EDE = ggplot(orig_ede, aes(x = descriptor, y = y_EDE, 
		group = demographic, color = demographic)) 
	if (scale_bool){
		y_EDE = y_EDE + geom_point(aes(x = factor(descriptor, level = descriptor_order), size = pct_demo_population) ) +
			labs(x = 'Optimization run', y = y_EDE_label, color = 'Demographic', size = 'Percent Total Population')
	} else{
		y_EDE = y_EDE + geom_point(aes(x = factor(descriptor, level = descriptor_order)),size = 5 )+ 
			labs(x = 'Optimization run', y = y_EDE_label, color = 'Demographic')
	}
	y_EDE = y_EDE +	ylim(y_min, y_max) + ggtitle(paste('Equity weighted', title_str)) +
		scale_color_discrete(labels = demographic_legend_dict)

	name = paste('orig', suffix, 'y_EDE.png', sep = '_')
	ggsave(name, y_EDE)
	
	#plot with avg_dist
	avg = ggplot(orig_ede, aes(x = descriptor, y = avg_dist, 
		group = demographic, color = demographic)) 
if (scale_bool){
		avg = avg + geom_point(aes(x = factor(descriptor, level = descriptor_order), size = pct_demo_population) ) + 
			labs(x = 'Optimization run', y = y_avg_label, color = 'Demographic', size = 'Percent Total Population')
	} else{
		avg = avg + geom_point(aes(x = factor(descriptor, level = descriptor_order) ),size = 5) + 
			labs(x = 'Optimization run', y = y_avg_label, color = 'Demographic')
	}
	avg = avg + ylim(y_min, y_max) + ggtitle(paste('Average', title_str)) + 
		scale_color_discrete(labels = demographic_legend_dict)
	name = paste('orig', suffix, 'avg.png', sep = '_')
	ggsave(name, avg)
}

ede_with_pop<- function(config_df_list){
	#join population data to ede graphs
	demo_pop <- config_df_list[[2]][ , .(total_population = sum(demo_pop)), by  = c('descriptor', 'demographic')]
	total_pop <- demo_pop[demographic == 'population', c('descriptor', 'total_population')]
	demo_pop <- merge(demo_pop, total_pop, by = 'descriptor')
	setnames(demo_pop, c('total_population.x', 'total_population.y'), c('total_demo_population', 'total_population'))
	demo_pop[ , pct_demo_population := total_demo_population/ total_population]
	edes_with_pop <- merge(config_df_list[[1]], demo_pop, by = c('descriptor', 'demographic'))
	return(edes_with_pop)
}

plot_original_optimized <- function(config_ede, orig_ede, suffix = ''){	
	#makes two plots, one showing the y_ede differences between the actual positioning and an equivalent optimized run; the other doing the same but with average distances

	#select the relevant optimized runs
	orig_num_polls <- unique(orig_ede$num_polls)
	optimized_run_dfs <- config_ede[num_polls %in% orig_num_polls]
	orig_and_optimal <- rbind(orig_ede, optimized_run_dfs)
	plot_election_edes(orig_and_optimal, paste0('and_optimal', suffix))
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
		labs(x = 'Number of polls', y = 'EV location', size = paste(demographic_legend_dict['population'], 'population'))

	ggsave('expanded_precinct_persistence.png')

	#also makes a panel of graphs showing which demographics are assigned to each poll
	ggplot(precinct_df[demographic != 'population',
		], aes(x = num_polls, y = id_dest)) +
		geom_point(aes(size = demo_pop)) + 
		labs(x = 'Number of polls', y = 'EV location', size = 'Population') + facet_wrap(~ demographic) +
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

#######
#make regression
#######

get_regression_data<-function(location, result_df){

	#get map data
	map_folders <- paste0(here(),'/datasets/census/tiger/', location, '/')
	map_files <- paste0(map_folders, list.files(map_folders)[endsWith(list.files(map_folders), 'tabblock20.shp')])

	map_data<- lapply(map_files, st_read)
	block_areas <- lapply(map_data, function(x){x[, c('GEOID20', 'ALAND20', 'AWATER20')]})
	if (length(block_areas)> 1){
		block_areas <- do.call(rbind, block_areas)
	}

	#merge block area data with result data
	#calculate population density (people/ km^2), pct white, pct black, population density quantile, and a fuzzy distance (max(distance_m, 100))
	regression_data <- merge(result_df, block_areas, by.x = 'id_orig', by.y = 'GEOID20', all.x = T)
	regression_data[ , `:=`(area = ALAND20 + AWATER20, pop_density_km = 1e6 *population/(ALAND20 + AWATER20), pct_white= 100 * white/population, pct_black = 100 *black/population)][ , density_pctile := rank(pop_density_km)/length(pop_density_km)][ , fuzzy_dist :=distance_m][fuzzy_dist <100, fuzzy_dist := 100]
	return(regression_data)
}

plot_predicted_distances<- function(regression_data, model){

	#pull out descriptors and density quantiles for linear plots
	pop_density_quantile <-quantile(regression_data$pop_density_km, c(.05, .25, .5, .75, .95))
	descriptor_list <- unique(regression_data$descriptor)
	density_dt <- CJ(descriptor_list, pop_density_quantile)
	pct_dt<- CJ(descriptor_list, c(.05, .95))
	setnames(density_dt, c('descriptor_list', 'pop_density_quantile'), c('descriptor', 'pop_density'))
	setnames(pct_dt, c('descriptor_list', 'V2'), c('descriptor', 'sim_pct_black'))

	#merge with the model coefficient data
	model_dt <- merge(model, density_dt, by = 'descriptor', allow.cartesian = TRUE)
	model_dt <- merge(model_dt, pct_dt, by = "descriptor", allow.cartesian = TRUE)

	#calculate the predicted distances
	model_dt[ , predicted_dist := intercept + density_coef*pop_density+(density_black_interaction_coef*pop_density+pct_black_coef)*sim_pct_black]

	dist_bounds <- c(.95*min(model_dt$predicted_dist), 1.05*max(model_dt$predicted_dist))
	#plot
	plot_pctile_pred<- function(pctile, names){
		ggplot(model_dt[pop_density == pctile, ], aes(x = sim_pct_black, y = predicted_dist, group = descriptor, color = descriptor)) + 
		geom_line() + ggtitle(paste0("Predicted distance traveled at ", names, "-ile density")) +
		ylim(dist_bounds[1],dist_bounds[2])
		ggsave(paste0("Pred_dist_at_",  names, ".png"))
	}

	good_names <- gsub('%', '', names(pop_density_quantile), fixed = T)
	mapply(function(pctile, pctile_name){plot_pctile_pred(pctile, pctile_name)}, pop_density_quantile, good_names)
}

plot_distance_by_density_black <- function(data, this_descriptor){
	ggplot(data[descriptor == this_descriptor, ], aes(x= pct_black, y = density_pctile)) +
	geom_point(aes(color = distance_m, size = population)) + 
	scale_color_viridis_c(limits = c(color_bounds[[1]], color_bounds[[2]]), name = "Distance to poll (m)") + xlim(c(0, 100)) + ylim(c(0,1)) + ggtitle('Distance to poll by Pct Black and Population Density Percentile')
	ggsave(paste0(this_descriptor, '_dist_by_density_black.png'))
}

plot_distance_by_density_black_3d <- function(data, this_descriptor){
	plot_ly(data[descriptor == this_descriptor, ], 
				x= ~pct_black, 
				y = ~density_pctile, 
				z = ~distance_m, 
				size = ~I(population*.3), 
				text = ~paste('Distance (m) :', distance_m, 
							'<br>Percent Black :', pct_black, 
							'<br>Population Density / km^2 :', pop_density_km, 
							'<br>Population Density Percentile :', density_pctile, '<br>Population :', population), 
				hoverinfo = "text", 
				mode = 'markers')%>% 
		layout(title = paste(this_descriptor, "Distance to Polls for Census Blocks"),
				scene = list(xaxis = list(title = 'Percent African American'),
				yaxis = list(title = 'Population Density (percentile)'),
				zaxis = list(title = 'Distance (m)', range =color_bounds)))
	htmlwidgets::saveWidget(as_widget(fig), paste0(this_descriptor, '_dist_by_density_black.html'))
}

calculate_pct_change <- function(data, reference_descriptor){

	data_wide <- dcast(data, id_orig ~descriptor, value.var = 'fuzzy_dist')
	cols <- names(data_wide)[names(data_wide) != 'id_orig']
	
	data_wide[, (cols) := lapply(.SD, function(x)(get(reference_descriptor) - x)/x), .SDcols = cols]

	dif_data<- melt(data_wide, id = c('id_orig'), variable = 'descriptor', value = 'pct_extra_in_2022')

	data <- merge(data, dif_data, by = c('id_orig', 'descriptor'))
	return(data)
}


plot_pct_change_by_density_black_3d <- function(data, this_descriptor){
	
	fig <- plot_ly(data[descriptor == this_descriptor, ], 
				x= ~pct_black, 
				y = ~density_pctile, 
				z = ~pct_extra_in_2022,
				size = ~I(population*.3), 
				text = ~paste('<br>Percent extra in 2022:', pct_extra_in_2022,
							'<br>Distance (m) :', fuzzy_dist, 
							'<br>Percent Black :', pct_black, 
							'<br>Population Density / km^2 :', pop_density_km, 
							'<br>Population Density Percentile :', density_pctile, '<br>Population :', population), 
				hoverinfo = "text", 
				mode = 'markers')%>% 
		layout(title = paste("Percent change in distance", gsub('_', ' ', this_descriptor),  "to 2022"),
				scene = list(xaxis = list(title = 'Percent African American'),
				yaxis = list(title = 'Population Density (percentile)'),
				zaxis = list(title = 'Percent Extra Distance in 2022')))

	htmlwidgets::saveWidget(as_widget(fig), paste0(this_descriptor, 'pct_diff_by_density_black.html'))
	return(fig)
}