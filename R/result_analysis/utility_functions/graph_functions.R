library(data.table)
library(ggplot2)
library(stringr)
library(here)
library(plotly)
library(DBI)
library(bigrquery)
library(yaml)

source('R/result_analysis/utility_functions/load_config_data.R')
source('R/result_analysis/utility_functions/storage.R')

TABLES = c("edes", "precinct_distances", "residence_distances", "results")
DEMO_COLS =  c("population", "hispanic","non_hispanic", "white", "black", "native", "asian", "pacific_islander", "other")

PRINT_SQL = FALSE





#########
#Get flags from the config folders or config file
#########
#get driving/ log flag from config data
set_global_flag<- function(config_dt_list, flag_type){
	#takes a data.table of config data (where rows are different files)
	#and checks that they all have the same driving or log flag in them
	#If they do, this is the global driving flag. If not, returns an error
	if (flag_type %in% names(config_dt_list)){
		flag_list <- sapply(config_dt_list[[flag_type]], as.logical)
		if (length(unique(flag_list))==1){
			global_driving_flag = unique(flag_list)
		}else{
			stop(paste0(flag_type, ' flags different in different files. Cannot set global value'))
		}
	} else{
		global_driving_flag = FALSE
	}
	return(global_driving_flag)
}

#If the config indicates that the analysis is for historical data only,
#this function is used to make non-historical runs 
#(e.g. outputs derived from potential config folder) return null

check_historic_flag<- function(null_arg, historic_flag = HISTORICAL_FLAG){
	if(!is.null(null_arg)){ #if the input is not null, the output shouldn't be
		return(FALSE)
	}
	if (historic_flag) {#the input is null and historical config
		return(TRUE)
	}else{#input is not NULL, but this is a historical config
		stop('HISTORICAL_FLAG is FALSE but argument NULL')
	}
}
#######
#Process config data to generate a descriptor field (for use in graph labels)
#######

select_varying_fields <- function(config_dt){
	#Each config folder/set should have exactly one field that varies
	#Therefore there should be exactly two (2) fields in config_dt that are not constant
	#NOTE: this function does not work if the config folder has only one file in it.
	#constant: file_name, and the field that varies in the folder
	#return a data.table with just these two.

	# Remove the database related columns that don't count as varying, if they exist
	config_dt_filtered <- copy(config_dt)
	cols_to_remove <- c("id", "created_at", "model_run_id", "run_at")
	config_dt_filtered[, (cols_to_remove) := NULL]

	#determine non-unique field
	unique_values_of_fields <- sapply(config_dt_filtered, function(x){length(unique(x))})
	varying_cols <- names(unique_values_of_fields)[unique_values_of_fields >1]

	#raise error if more than 2 non-unique fields (1 in addition to file_name / config_name)
	if (length(varying_cols) != 2){
		stop(paste('Too many fields vary across collection of config files:', paste(varying_cols, collapse = ', ')))
	}

	#select the parameter of interest
	result_dt <- config_dt_filtered[ , ..varying_cols]
	return(result_dt)
}

create_descriptor_field <- function(config_dt, field_of_interest){
	#1) identify the (unique) field that changes
	#1a) if the config folder has a single file in it, the string "field_of_interest"
	#2) add a descriptor field and return the three columns in a data.table

	#1) get name of varying field
	if (nrow(config_dt)>1){
		varying_dt <- select_varying_fields(config_dt)
	} else if (nrow(config_dt)==1){
		#if there is only one row, and field of interest isn't specified, raise an error
		if (field_of_interest == ''){
			stop('only one config_name in config_set, but no field of interest specified')
		} 
		#1a) otherwise, check that that the field of interest is in the config data, 
		#and create varying_dt. Else, throw error
		if (field_of_interest %in% names(config_dt)){
			varying_cols <- c(field_of_interest, 'config_name')
			varying_dt <- config_dt[ , ..varying_cols]}
		else{
			stop('FIELD_OF_INTEREST value is not a valid config field')
		}
	} else {
		stop('there are no config files in the config folder')
	}

	#2) create a descriptor field
	#identify the field name
	varying_field<- names(varying_dt)[names(varying_dt) != 'config_name']
	#paste the name of the varying field with its value
	varying_dt <- varying_dt[, descriptor_pre:= varying_field
						   ][, descriptor := do.call(paste, c(.SD, sep = '_')), .SDcols = c('descriptor_pre', varying_field)][ , descriptor_pre:= NULL]
	return(varying_dt)
}

#function to set certain descriptors as desired
change_descriptors <- function(df, descriptor_dict){
	#if the descriptor dictionary is NULL, then do nothing
	if(is.null(descriptor_dict)){return(df)}

	#otherwise, there is data in the dictionary. Check that this is consisent with the 
	#descriptor data in the df
	generated_descriptors <- unique(df$descriptor)
	dict_descriptors <- names(descriptor_dict)
	missing_from_dict <- setdiff(generated_descriptors, dict_descriptors)
	if(length(missing_from_dict)>0){
		missing_field_str<- paste(missing_from_dict, collapse = ' ')
		missing_str <- paste('mistaken entries in config: ', missing_field_str)
	}else{missing_str <- NULL}
	extra_in_dict <- setdiff(dict_descriptors, generated_descriptors)
	if(length(extra_in_dict)>0){
		extra_field_str <- paste(extra_in_dict, collapse = ' ')
		extra_str <- paste('mistaken entries in config: ', extra_field_str)
	}else{extra_str <- NULL}
	#if either missing from dict or extra in dict are non-empty, stop
	if (length(missing_from_dict) > 0 | length(extra_in_dict) >0){
		stop(paste0('Missmatch between descriptor values given in config and generated algorithmically:\n', 
					missing_str, '\n', extra_str))
	}
	
	#assuming consistency, replace values in df
	#1. turn dictionary into data.table
	descriptor_dt <- data.table(old_descriptor = names(descriptor_dict), new_descriptor = descriptor_dict)
	#2. merge and rename columns
    df_renamed <-  merge(df, descriptor_dt, by.x = 'descriptor', by.y = 'old_descriptor', all.x = TRUE)
	df_renamed[ , descriptor := NULL]
	setnames(df_renamed, c('new_descriptor'), c('descriptor'))
return(df_renamed)
}

######
#Functions to read in results
#and add descriptor field as needed
######


load_results_from_csv <-function(config_dt, result_type){
	#select which results we want
	#TODO: Check that this works for multiple locations
	# get location(s) and config folder
	location <- unique(config_dt$location)
	config_folder <- unique(config_dt$config_set)
	#get result folder(s)
	result_folder <-paste0('datasets/results/', location, '_results/')
	#extract files
	files <- list.files(result_folder)
	#select files containing config_folder and result_type in name
	files <- files[grepl(paste0(config_folder, '.'), files, ignore.case = TRUE) &grepl(result_type, files, ignore.case = TRUE)]
	#label with config name
	config_names <- gsub(paste0('.*', config_folder, '\\.'), '', files)
	config_names <- gsub(paste0('_', result_type, '\\.csv'), '', config_names)
	names(files) <- config_names
	#put together to form a file path
	file_path <- paste0(result_folder, files)
	names(file_path) <- names(files)
	
	#read data, add config_set and config_name columns
	#note, this needs a local function
	dt_list <- lapply(file_path, fread)
	names(dt_list) <- names(file_path)
	dt_list_appended <- mapply(function(data, list_name){data[, config_name:=list_name][ , config_set := config_folder][ , location := location]}, dt_list, names(dt_list), SIMPLIFY = FALSE)
	
	#combine into one df
	big_dt <- do.call(rbind, dt_list_appended)
	return(big_dt)
}

set_results_column_names <- function(results_dt) {
	mappings <- list(y_ede = "y_EDE")

	# Rename columns based on mappings
	for (src in names(mappings)) {
		if (src %in% colnames(results_dt)) {
			setnames(results_dt, src, mappings[[src]])
		}
	}
}

load_results_from_db <-function(table_name, model_run_ids, con = POLLING_CON){
	if (length(model_run_ids) < 1) {
		return(NULL)
	}

	model_run_ids_string <- paste0("'", model_run_ids, "'", collapse = ", ")

	sql <- paste0("SELECT * FROM ", table_name, " WHERE model_run_id IN (", model_run_ids_string, ")")

	if (PRINT_SQL) print(sql)

	big_tbl <- dbGetQuery(con, sql)
	big_dt <- as.data.table(big_tbl)

	# Set the correct case instead of database case for column names
	set_results_column_names(big_dt)
	return(big_dt)
}

assign_descriptor_to_result<- function(config_dt, result_type, field_of_interest, read_from_csv,
										 descriptor_dict){
	#read in and format all the results data assocaited to a
	#given config data
	#result_type: in c((ede, precinct, residence, results)
	#field_of_interest: string indicating the field to be used for a descriptor (in case the config folder has only 1 file)
	#returns: list(ede_df, precinct_df, residence_df, result_df)
	
	#read in descriptor data
	vary_dt <- create_descriptor_field(config_dt, field_of_interest)
	#drop varying field (because this changes across config_set)
	vary_dt <- vary_dt [ , .(config_name, descriptor)]
	
	
	#read in output data
	if (read_from_csv){
		result_type_dt <- load_results_from_csv(config_dt, result_type)
	} else {
		model_run_ids <- unique(config_dt$model_run_id)
		extras_table_name = paste0(result_type, '_extras')

		result_type_dt <- load_results_from_db(table_name=extras_table_name, model_run_ids)
	}
	
	#merge output and descriptor data
	complete_dt <- merge(vary_dt, result_type_dt, by = c('config_name'))

	#change to custom descriptors if desired
	complete_dt <- change_descriptors(complete_dt, descriptor_dict)

	#fix data types (only needed for csv)
	if ('id_dest' %in% names(complete_dt)){
		complete_dt[ , id_dest:= as.character(id_dest)]}
	if ('id_orig' %in% names(complete_dt)){
		complete_dt[ , id_orig:= as.character(id_orig)]}

	return(complete_dt)
}

read_result_data<- function(config_dt, field_of_interest = '', descriptor_dict = DESCRIPTOR_DICT, 
							tables = TABLES, read_from_csv = READ_FROM_CSV){
	#read in and format all the results data associated to a
	#given config data.
	#field_of_interest: string indicating the field to be used for a descriptor (in case the config folder has only 1 file)
	#returns: list(ede_df, precinct_df, residence_df, result_df)

	#if config_dt is NULL, and HISTORIC_FLAG return NULL
	if(check_historic_flag(config_dt)){
		return(NULL)
	}
	
	#get a list of result data with a descriptor column attached to each data.table
	df_list<- lapply(tables, function(x){assign_descriptor_to_result(config_dt, x, field_of_interest, read_from_csv, descriptor_dict)})
	names(df_list) <- tables

	#label each dataset wtih number of polls and blocks
	num_polls <- df_list$precinct_distances[ , .(num_polls = .N/6), by = descriptor]
	num_residences <- df_list$residence_distances[ , .(num_residences = .N/6), by = descriptor]
	nums_to_join <- merge(num_polls, num_residences, all = T)
	appended_df_list <- lapply(df_list, function(df){merge(df, nums_to_join, by = 'descriptor', all.x = T)})

	# Track information about configs used in this analsysis
	mapply(add_config_info_to_graph_file_manifest, config_dt$id, config_dt$config_set, config_dt$config_name)
	sapply(config_dt$model_run_id, add_model_run_id_to_graph_file_manifest)

	return(appended_df_list)
}

#######
#useful functions for making plots
#######

#dictionary for labels

demographic_legend_dict <- c(
	'asian' = 'Asian (not PI)',
	'black' = 'African American',
	'white' = 'White',
	'hispanic' = 'Latine',
	'native' = 'First Nations',
	'population' = 'Total')

#helper function to make graph titles according to flag values
make_flag_strs<- function(driving_flag, log_flag){
	#make flag dependent labels
	driving_str = ' straight line '
	log_str = ''
	if (driving_flag){driving_str = ' driving '} 
	#if (log_flag){log_str = 'log '}
	return(as.list(c(driving_str = driving_str, log_str = log_str)))
}

#helper function to combine ede data from different config folders
combine_different_runs<- function(df_list){
	#takes a list of ede data generated from config folders and, if the descriptors
	#are unique, combines them into one dataframe for plotting

    #check for descriptor uniqueness
    all_descriptors <- unlist(lapply(df_list, function(x){unique(x$descriptor)}))
    if(length(unique(all_descriptors))< length(all_descriptors)){
        stop('The data.tables being combined have descriptors in common. Please rename.')
    }
    #combine data
    df<- do.call(rbind, df_list)
    return(df)
}

#join population data to ede graphs in order to get population scaled graphs
ede_with_pop<- function(config_df_list){
	#aggregate population by demographic and descriptor
	demo_pop <- config_df_list$precinct_distances[ , .(total_population = sum(demo_pop)), by  = c('descriptor', 'demographic')]
	#extract total population for each descriptor
	total_pop <- demo_pop[demographic == 'population', c('descriptor', 'total_population')]
	#add a total population column to demo_pop
	demo_pop <- merge(demo_pop, total_pop, by = 'descriptor')
	setnames(demo_pop, c('total_population.x', 'total_population.y'), c('total_demo_population', 'total_population'))
	#calculate the percent of the total population attributed to each demographic group
	demo_pop[ , pct_demo_population := total_demo_population/ total_population]
	#merge this data into the ede data
	edes_with_pop <- merge(config_df_list$edes, demo_pop, by = c('descriptor', 'demographic'))
	return(edes_with_pop)
}

#######
#plotting functions
#######

#####edes for all descriptors in a config_set######

#makes a plot showing how y_EDEs change for each demographic group as the
#number of polls is increased
plot_poll_edes<-function(ede_df, driving_flag = DRIVING_FLAG, log_flag = LOG_FLAG){

	flag_strs <- make_flag_strs(driving_flag, log_flag)
	
	title_str = paste0('Equity weighted', flag_strs$driving_str, 'distance to poll by demographic')
	y_str = paste0('Equity weighted', flag_strs$driving_str, 'distance (', flag_strs$log_str, 'm)')

	graph = ggplot(ede_df, aes(x = num_polls, y = y_EDE,
		group = demographic, color = demographic, shape = demographic)) +
		geom_line()+ geom_point()+
		labs(x = 'Number of polls', y = y_str, title = title_str, color = 'Demographic', shape = 'Demographic')+
		scale_color_discrete(labels = demographic_legend_dict) +
		scale_shape(labels = demographic_legend_dict)
	#TODO: make this work
	#if(log_flag){graph = graph + scale_y_continuous(trans="log2")

	graph_file_path = 'demographic_edes.png'
	add_graph_to_graph_file_manifest(graph_file_path)
	ggsave(graph_file_path)
}

#like plot_poll_edes, but plots just the y_edes for the
# population as a whole, and not demographic groups
plot_population_edes <- function(ede_df, driving_flag = DRIVING_FLAG, log_flag = LOG_FLAG){
	flag_strs <- make_flag_strs(driving_flag, log_flag)

	title_str = paste0('Equity weighted', flag_strs$driving_str, 'distance to poll')
	y_str = paste0('Equity weighted', flag_strs$driving_str, 'distance (', flag_strs$log_str, 'm)')


	graph = ggplot(ede_df[demographic == 'population', ], aes(x =  num_polls, y = y_EDE))+
		geom_line()+ geom_point()+
		labs(x = 'Number of polls', y = y_str, title = title_str)

	graph_file_path = 'population_edes.png'
	add_graph_to_graph_file_manifest(graph_file_path)
	ggsave(graph_file_path)
}

#makes a plot showing how the y_EDEs for multiple config_sets change 
#as the number of polls is increased, for a specified demographic_group 
plot_multiple_edes<-function(ede_list, demo_grp, driving_flag = DRIVING_FLAG, log_flag = LOG_FLAG){
	ede_df <- do.call(rbind, ede_list)

	flag_strs <- make_flag_strs(driving_flag, log_flag)
	
	title_str = paste0('Equity weighted', flag_strs$driving_str, 'distance to poll by demographic')
	y_str = paste0('Equity weighted', flag_strs$driving_str, 'distance (', flag_strs$log_str, 'm)')

	ggplot(ede_df[demographic == demo_grp, ], aes(x = num_polls, y = y_EDE,
		group = descriptor, color =  descriptor, shape = demo_grp)) +
		geom_line()+ geom_point()+
		labs(x = 'Number of polls', y = y_str, title = title_str, color = "Run Type", shape = 'Demographic')+
		scale_shape_discrete(labels = demographic_legend_dict) +
		scale_color_manual(breaks = c('Intersecting', 'Contained'), values = c('red','darkviolet'))

	graph_file_path = paste0(demo_grp, '_compare_demographic_edes.png')
	add_graph_to_graph_file_manifest(graph_file_path)
	ggsave(graph_file_path)
}

#####historic and optimize edes ######

#makes two plots, one showing the y_ede the other avg distance
#showing how these variables change across the included runs
plot_historic_edes <- function(orig_ede, suffix = '', driving_flag = DRIVING_FLAG, log_flag = LOG_FLAG){

	#set x axis label order
	descriptor_order <- unique(orig_ede$descriptor)

	#select y axis bounds
	all_y_values = c(c(orig_ede$avg_dist), c(orig_ede$y_EDE))
	y_min = min(all_y_values)
	y_max = max(all_y_values)

	#set point size
	#does data contain scaling data
	scale_bool = 'pct_demo_population' %in% names(orig_ede)
	
	flag_strs <- make_flag_strs(driving_flag, log_flag)

	#labels for various types of data
	y_EDE_label = paste0('Equity weighted', flag_strs$driving_str, 'distance (', flag_strs$log_str, 'm)')
	y_avg_label = paste0('Average', flag_strs$driving_str, 'distance (', flag_strs$log_str, 'm)')
	title_str = paste0(flag_strs$log_str, flag_strs$driving_str, 'distance by demographic and optimization run')
	#plot with y_EDE
	y_EDE = ggplot(orig_ede, aes(x = descriptor, y = y_EDE,
		group = demographic, color = demographic, shape = demographic))
	if (scale_bool){
		y_EDE = y_EDE + geom_point(aes(x = factor(descriptor, level = descriptor_order), size = pct_demo_population) , alpha = .5) +
			labs(x = 'Optimization run', y = y_EDE_label, shape = 'Demographic', color = 'Demographic', size = 'Percent Total Population')
	} else{
		y_EDE = y_EDE + geom_point(aes(x = factor(descriptor, level = descriptor_order)),size = 5, alpha = .5)+
			labs(x = 'Optimization run', y = y_EDE_label, shape = 'Demographic', color = 'Demographic')
	}
	y_EDE = y_EDE +	#ylim(y_min, y_max) + 
				ggtitle(paste('Equity weighted', title_str)) +
				scale_color_discrete(labels = demographic_legend_dict)+
				scale_shape_discrete(labels = demographic_legend_dict)

	graph_file_path = paste('orig', suffix, 'y_EDE.png', sep = '_')
	add_graph_to_graph_file_manifest(graph_file_path)
	ggsave(graph_file_path, y_EDE)

	#plot with avg_dist
	avg = ggplot(orig_ede, aes(x = descriptor, y = avg_dist,
		group = demographic, color = demographic, shape = demographic))
	if (scale_bool){
		avg = avg + geom_point(aes(x = factor(descriptor, level = descriptor_order), size = pct_demo_population) , alpha = .5) +
			labs(x = 'Optimization run', y = y_avg_label, shape = 'Demographic', color = 'Demographic', size = 'Percent Total Population')
	} else{
		avg = avg + geom_point(aes(x = factor(descriptor, level = descriptor_order) ),size = 5, alpha = .5) +
			labs(x = 'Optimization run', y = y_avg_label, shape = 'Demographic', color = 'Demographic')
	}
	avg = avg + #ylim(y_min, y_max) + 
			ggtitle(paste('Average', title_str)) +
			scale_color_discrete(labels = demographic_legend_dict) +
			scale_shape_discrete(labels = demographic_legend_dict)

	graph_file_path = paste('orig', suffix, 'avg.png', sep = '_')
	add_graph_to_graph_file_manifest(graph_file_path)
	ggsave(graph_file_path, avg)
}


#compares optimized runs with historical runs having the same number of
#polls (via plot_historical_edes)
plot_original_optimized <- function(config_ede, orig_ede, suffix = '', driving_flag = DRIVING_FLAG, log_flag = LOG_FLAG){
	#select the relevant optimized runs
	orig_num_polls <- unique(orig_ede$num_polls)
	config_num_polls <- unique(config_ede$num_polls)
	optimization_num_polls<- max(intersect(orig_num_polls, config_num_polls))
	optimized_run_dfs <- config_ede[num_polls == optimization_num_polls]
	orig_and_optimal <- rbind(orig_ede, optimized_run_dfs)
	plot_historic_edes(orig_and_optimal, paste0('and_optimal', suffix), driving_flag, log_flag)

}


#a plot showing which precincts are used for which number of polls
#also makes a panel of graphs showing which demographics are assigned to each poll
plot_precinct_persistence <- function(precinct_df){
	ggplot(precinct_df[demographic == 'population',
		], aes(x = num_polls, y = id_dest)) +
		geom_point(aes(size = demo_pop)) +
		labs(x = 'Number of polls', y = 'EV location', size = paste(demographic_legend_dict['population'], 'population'))

	graph_file_path = 'precinct_persistence.png'
	add_graph_to_graph_file_manifest(graph_file_path)
	ggsave(graph_file_path)

	ggplot(precinct_df[demographic != 'population',
		], aes(x = num_polls, y = id_dest)) +
		geom_point(aes(size = demo_pop)) +
		labs(x = 'Number of polls', y = 'EV location', size = 'Population') + facet_wrap(~ demographic) +
		theme(legend.position = c(0.9, 0.2))

	graph_file_path = 'precinct_persistence_demographic.png'
	add_graph_to_graph_file_manifest(graph_file_path)
	ggsave(graph_file_path)
}

#make boxplots of the average distances traveled and the y_edes at each run
plot_boxplots <- function(residence_df,log_flag = LOG_FLAG, driving_flag = DRIVING_FLAG){
	flag_strs <- make_flag_strs(driving_flag, log_flag)

	res_pop <- residence_df[demographic == 'population',
		]
	#avg distance
	ggplot(res_pop, aes(x = num_polls, y = avg_dist, group = descriptor)) +
		stat_boxplot(geom = "errorbar")+
		geom_boxplot(outlier.shape = NA) +
		scale_y_log10(limits = c(500,10500)) +
		labs(x = 'Number of polls', y = paste0("Avg",  flag_strs$driving_str, "distance (", flag_strs$log_str, ' m)'))

	graph_file_path = 'avg_dist_distribution_boxplots.png'
	add_graph_to_graph_file_manifest(graph_file_path)
	ggsave(graph_file_path)
}

#make histogram of the average distances traveled in the historical and ideal situations
plot_orig_ideal_hist <- function(orig_residence_df, config_residence_df, ideal_num, log_flag = LOG_FLAG, driving_flag = DRIVING_FLAG){
	flag_strs <- make_flag_strs(driving_flag, log_flag)

	orig_residence_df <- orig_residence_df[demographic == 'population', ]
	ideal_residence_df <- config_residence_df[demographic == 'population', ][num_polls == ideal_num, ]
	res_pop_orig_and_ideal <- rbind( ideal_residence_df, orig_residence_df)

	#avg_distance
	ggplot(res_pop_orig_and_ideal, aes(x = avg_dist, fill = descriptor)) +
		geom_histogram(aes(weight = demo_pop), position = "dodge", alpha = 0.8)+
		labs(x = paste0("Avg",  flag_strs$driving_str, "distance (", flag_strs$log_str, ' m)'), y = 'Number of people', fill = 'Optimization Run')
	graph_file_path = 'avg_dist_distribution_hist.png'
	add_graph_to_graph_file_manifest(graph_file_path)
	ggsave(graph_file_path)
}

plot_demographic_hist<- function(df, demo, flag_strs){

	y_str = paste0('Number of ', demo, ' people')
	title_str = paste0('Distribution of distances traveled by ', demo, ' people by year or optimization')
	hist = ggplot(df[demographic == demo, ], aes(x = avg_dist, fill = descriptor)) +
		geom_histogram(aes(weight = demo_pop), position = "dodge", alpha = 0.8)+
		labs(x = paste0("Avg",  flag_strs$driving_str, "distance (", flag_strs$log_str, ' m)'), y = y_str, title =  title_str, fill = 'Optimization Run') + scale_x_continuous(transform = 'log')

	graph_file_path = paste0(demo, ' avg_dist_distribution_hist.png')
	add_graph_to_graph_file_manifest(graph_file_path)
	ggsave(graph_file_path)
	return(hist)
}

plot_original_optimized_demographic_hists <- function(config_residence_df, orig_residence_df, demographic_list = DEMOGRAPHIC_LIST, driving_flag = DRIVING_FLAG, log_flag = LOG_FLAG){
	flag_strs <- make_flag_strs(driving_flag, log_flag)

	#select the relevant optimized runs
	orig_num_polls <- unique(orig_residence_df$num_polls)
	config_num_polls <- unique(config_residence_df$num_polls)
	optimization_num_polls<- max(intersect(orig_num_polls, config_num_polls))
	optimized_run_dfs <- config_residence_df[num_polls == optimization_num_polls]
	orig_and_optimal <- rbind(orig_residence_df, optimized_run_dfs)
	descriptor_list <- unique(orig_and_optimal$descriptor)

	demographic_hists = lapply(demographic_list, function(x)plot_demographic_hist(orig_and_optimal, x, flag_strs))
}


#plot of population densities by block, ordered by density
plot_population_densities <- function(density_df){
	ggplot(density_df[population != 0, ]) + 
	   geom_point(aes(reorder(id_orig, pop_density_km), y = pop_density_km)) +
	   labs(title = 'Block group population density / km', x = 'Density ordered Census Blocks', y = 'Population density / km') +
	   theme(
		axis.text.x = element_blank(),
        axis.ticks.x=element_blank())
	graph_file_path = 'population_density.png'
	add_graph_to_graph_file_manifest(graph_file_path)
	ggsave(graph_file_path)
}

#plot of average distances traveled by demographic groups, aggregated 
#at the block group level, ordered by population density
#log / log scale, with best fit lines
plot_density_v_distance_bg <- function(bg_density_data, county, demo_list, log_flag = LOG_FLAG, driving_flag = DRIVING_FLAG){
	
	#set graph y axis bounds. if min_distance == 0 m, make 1m
	min_dist = min(bg_density_data[demographic %in% demo_list, ]$demo_avg_dist, na.rm = TRUE)
	max_dist = max(bg_density_data[demographic %in% demo_list, ]$demo_avg_dist, na.rm = TRUE)
	if (min_dist == 0){min_dist = min_dist + .01}
    y_bounds = c(min_dist,max_dist)

	#trim log density outliers
	trimmed <- bg_density_data[abs(z_score_log_density)<4, ]

    descriptor_graph <- function(descriptor_str, demo_list, y_bounds){   
		flag_strs <- make_flag_strs(driving_flag, log_flag)
	
		title_str = paste0('Average', flag_strs$driving_str, 'distance to poll by demographic and block group')
		y_str = paste0(paste0("Avg",  flag_strs$driving_str, "distance (", flag_strs$log_str, ' m)'))

        ggplot(trimmed[descriptor == descriptor_str & demographic %in% demo_list, ] , aes(x = pop_density_km, y = demo_avg_dist, group = demographic, color = demographic)) +
            geom_point(alpha = .7, aes(size = demo_pop )) + geom_smooth(method=lm, mapping = aes(weight = demo_pop), se= F) + scale_x_continuous(trans = 'log10') + scale_y_log10(limits = y_bounds) + 
            labs(title = title_str, 
                subtitle = gsub("_", " ", paste(county, descriptor_str)), y = y_str , 
				x = "Block group population density (people/ km^2)", size = 'Population', color = 'Demographic') + 
				scale_color_discrete(labels = demographic_legend_dict[demo_list])
		graph_file_path = paste(county, descriptor_str, "avg distance.png")
		add_graph_to_graph_file_manifest(graph_file_path)
		ggsave(graph_file_path)
    }
    descriptors = unique(trimmed$descriptor)
    sapply(descriptors, function(x){descriptor_graph(x, demo_list, y_bounds)})
    }

