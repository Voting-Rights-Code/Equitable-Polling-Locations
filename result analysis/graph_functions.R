library(data.table)
library(ggplot2)
library(stringr)
library(here)
library(plotly)
library(DBI)
library(bigrquery)
library(yaml)

#######
#DB connection
#######
define_connection<- function(read_from_csv = READ_FROM_CSV, project = PROJECT, dataset = DATASET){
	if (!READ_FROM_CSV){
    	con <- dbConnect(
        	bigrquery::bigquery(),
        	project = PROJECT,
        	dataset = DATASET
    	)
	} else{ con = NULL}
	return(con)
}

#######
#Read config files
#######


config_to_list <- function(config_folder, config_name){
	#Reads yamls in config_folder, apppends config name as a field to yaml data
	config_file <- paste(config_folder, config_name, sep = '/')
	config_list <- read_yaml(config_file)
	config_list <- c(config_list, config_name = sub('.yaml', '', config_name))
	return(config_list)
}

read_config <- function(config_folder){
	#returns a list of lists of all config files in config folder, 
	#with the file name added as a field
		
	#get file names
	file_names <- list.files(config_folder)

	#then create a list of list
	config_list <- lapply(file_names, function(x){config_to_list(config_folder, x)})
	return(config_list)
}

config_file_fields <- function(config_list){
	#checks that a given list of config files all have the same set of fields
	#if yes, returns the fields. Otherwise, returns an error

	#fields for each config file
	fields <- unique(lapply(config_list, names))
	#raise error if each config file does not have the same content
	if (length(fields)!= 1){
		stop('Config files have different fields')
	} 
	return(fields)	
}

collapse_fields <- function(config){
	#In order to put the configs into a list, for each config field that is a list
	#turn it into a pipe separated string, also change NULLs to NAs 
	
	#change nulls to NAs
	config <- lapply(config, function(x) {if(is.null(x)){x <- NA}else{x}})
	#collapse lists
	config <- lapply(config, function(x){paste(x[order(x)], collapse = '|')})
	return(config)
}

convert_configs_to_dt <- function(config_list){
	#check if each config in the list has the same fields
	fields <- config_file_fields(config_list)
	#collapse lists to strings
	collapsed_config_list <- lapply(config_list, function(x){collapse_fields(x)})
	#make this a data.table
	config_dt <- rbindlist(collapsed_config_list)
	return(config_dt)
}

read_config_folder_from_file <- function(config_folder){
	#read config folder data from file
	config_list <- read_config(config_folder)
	config_dt <- convert_configs_to_dt(config_list)
	return(config_dt)
}

read_config_set_from_db <- function(config_set, columns, con=POLLING_CON){
	#read indicated columns from config set data in database
	comma_sep_colls = paste(columns, collapse = ',')
	sql <- paste0("SELECT ", comma_sep_colls, " FROM configs WHERE config_set =  '", config_set, "'")
	config_tbl <- dbGetQuery(con, sql)
	config_dt <- as.data.table(config_tbl)
	return(config_dt)
}


#######
#Check that location and folders valid
#Load the data if they are
#######
check_config_folder_valid <- function(config_folder, read_from_csv, con){
	#chech that the config folder / set is valid
	if (read_from_csv){
		#raise error if config folder not a directory
		if (!dir.exists(config_folder)){
    		stop('Config folder does not exist on file')
		}
	} else{
		#raise error if config set not in database
		config_dt <- read_config_set_from_db(config_folder, 'config_set')
		if (nrow(config_dt) == 0){
			stop('Config set does not exist in database')
		}
	}
}

check_location_valid <- function(location, config_dt){
	#raise error if config folder does not contain a file with 
	#given location or config set does not contain data with
	#given location
	locations_in_config_folder <- unique(config_dt$location)
	missing_locations <- setdiff(location, locations_in_config_folder)
	if (length(missing_locations)>0){
    	stop(paste('Given config folder does not contain data for the following location(s):', missing_locations))
	}
}

#Read in config data
load_config_data <- function(location, config_folder, read_from_csv = READ_FROM_CSV, con = POLLING_CON){
	#check that the config folder is valid, and contains data for the location, then loads data.

	#check that config folder valid
	check_config_folder_valid(config_folder, read_from_csv, con)

	#if it is, load the data
	if(read_from_csv){
		config_dt <- read_config_folder_from_file(config_folder)
	} else{
		config_dt <- read_config_set_from_db(config_folder, '*')
	}

	#then check that the location is in the data
	check_location_valid(location, config_dt)

	#if all checks pass, convert to data.table and return data
	config_dt <- as.data.table(config_dt)
	return(config_dt)
}

#########
#Get a driving flag from the config folders
#########
get_driving_flag <- function(config_dt){
	#given a config folder, return the overall driving field value for the folder
	#If driving field is missing, return false.
	#If driving field varies in the config file, return an error
	#Otherwise, return the unique value in the field.
	if (!('driving' %in% names(config_dt))){ #if the flag not present, false
		driving_flag <- FALSE
	} else if(length(unique(config_dt$driving))>1){#if this is the flag that varies, not sure how to handle
		stop('Driving flag not consistent in config set')
	} else{#otherwise pull driving flag from unique value in this field
		driving_flag <- unique(config_dt$driving)
	}
	return(driving_flag)
}

set_global_driving_flag<- function(config_dt_list){
	#takes a list of config folders and checked that they all have the same driving flag in them
	#If they do, this is the global driving flag. If not, returns an error
	driving_flag_list <- sapply(config_dt_list, get_driving_flag)
	if (length(unique(driving_flag_list))==1){
    	global_driving_flag = unique(driving_flag_list)
	}else{
    	stop('driving flags different in different files. Cannot set global value')
	}
	return(global_driving_flag)
}

#######
#Process config files to generate graph labels
#######

select_varying_fields <- function(config_dt){
	#Each config folder/set should have exactly one field that varies
	#Therefore there should be exactly two (2) fields in config_dt that are not
	#NOTE: this function does not work if the config folder has only one file in it.
	#constant: file_name, and the field that varies in the folder
	#return a data.table with just these two.

	#determine non-unique field
	unique_values_of_fields <- sapply(config_dt, function(x){length(unique(x))})
	varying_cols <- names(unique_values_of_fields)[unique_values_of_fields >1]
	#raise error if more than 2 non-unique fields (1 in addition to file_name / config_name)
	if (length(varying_cols) != 2){
		stop(paste('Too many fields vary across collection of config files:', paste(varying_cols, collapse = ', ')))
	} 
	#select the parameter of interest
	result_dt <- config_dt[ , ..varying_cols]
	return(result_dt)
}

process_configs_dt <- function(config_dt, field_of_interest){
	#1) identify the (unique) field that changes
	#1a) if the config folder has a single file in it, the string "field_of_interest"
	#2) add a descriptor field and return the three columns in a data.table
	
	#1) get name of varying field
	if (nrow(config_dt)>1){
		varying_dt <- select_varying_fields(config_dt)
	} else if (nrow(config_dt)==1){
		varying_cols <- c(field_of_interest, 'config_name')
		varying_dt <- config_dt[ , ..varying_cols]
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

######
#Functions to read in results
######

load_output_from_csv <-function(config_dt, result_type){
	#select which results we want
	#TODO: Check that this works for multiple locations
	# get location(s) and config folder
	location <- unique(config_dt$location) 
	config_folder <- unique(config_dt$config_set)
	#get result folder(s)
	result_folder <-paste(location, 'results/', sep = '_')
	#extract files
	files <- list.files(result_folder)
	#select files containing config_folder and result_type in name
	files <- files[grepl(paste0(config_folder, '\\.'), files) &grepl(result_type, files)] 
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
	dt_list_appended <- mapply(function(data, list_name){data[, config_name:=list_name][ , config_set := config_folder]}, dt_list, names(dt_list), SIMPLIFY = FALSE)

	#combine into one df
	big_dt <- do.call(rbind, dt_list_appended)
	return(big_dt)
}

load_output_from_db <-function(config_dt, result_type, con = POLLING_CON){
	config_set <- unique(config_dt$config_set)
	sql <- paste0("SELECT * FROM ", result_type," WHERE config_set = '", config_set, "'")
	big_tbl <- dbGetQuery(con, sql)
	big_dt <- as.data.table(big_tbl)
	return(big_dt)
}

assign_descriptor<- function(config_dt, result_type, field_of_interest, read_from_csv = READ_FROM_CSV){
	#read in and format all the results data assocaited to a 
	#given config data
	#result_type: in c((ede, precinct, residence, results)
	#field_of_interest: string indicating the field to be used for a descriptor (in case the config folder has only 1 file)
	#returns: list(ede_df, precinct_df, residence_df, result_df)
	
	#read in descriptor data
	vary_dt <- process_configs_dt(config_dt, field_of_interest)
	#drop varying field (because this changes across config_set)
	vary_dt <- vary_dt [ , .(config_name, descriptor)]
	
	#read in output data
	if (read_from_csv){
		result_type_dt <- load_output_from_csv(config_dt, result_type) 
	} else {
		result_type_dt <- load_output_from_db(config_dt, result_type)
	}
	
	#merge data
	complete_dt <- merge(vary_dt, result_type_dt)	
	
	#fix data types (only needed for csv)
	if ('id_dest' %in% names(complete_dt)){
		complete_dt[ , id_dest:= as.character(id_dest)]}
	if ('id_orig' %in% names(complete_dt)){
		complete_dt[ , id_orig:= as.character(id_orig)]}
	
	return(complete_dt)
}

read_result_data<- function(config_dt, field_of_interest = '', tables = TABLES){
	#read in and format all the results data assocaited to a 
	#given config data.
	#field_of_interest: string indicating the field to be used for a descriptor (in case the config folder has only 1 file)
	#returns: list(ede_df, precinct_df, residence_df, result_df)
	
	#read output data into a list with a descriptor column attached
	df_list<- lapply(tables, function(x){assign_descriptor(config_dt, x, field_of_interest)})
	names(df_list) <- tables

	#label descriptors with polls and residences
	num_polls <- df_list$precinct_distances[ , .(num_polls = .N/6), by = descriptor]
	num_residences <- df_list$residence_distances[ , .(num_residences = .N/6), by = descriptor]
	nums_to_join <- merge(num_polls, num_residences, all = T)

	appended_df_list <- lapply(df_list, function(df){merge(df, nums_to_join, by = 'descriptor', all.x = T)})

	return(appended_df_list)
}



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

#makes a plot showing how y_EDEs change for each demographic group as the 
#number of polls is increased

#DOES NOT ACCOMODATE DRIVING DISTANCES
plot_poll_edes<-function(ede_df){
	ggplot(ede_df, aes(x = num_polls, y = y_EDE, 
		group = demographic, color = demographic)) +
		geom_line()+ geom_point()+ 
		labs(x = 'Number of polls', y = 'Equity weighted distance (m)', color = 'Demographic')+ 
		scale_color_discrete(labels = demographic_legend_dict)
	ggsave('demographic_edes.png')
}

plot_multiple_edes<-function(ede_list, demo_grp){
	ede_df <- do.call(rbind, ede_list)
	ggplot(ede_df[demographic == demo_grp, ], aes(x = num_polls, y = y_EDE, 
		group = descriptor, color =  descriptor, shape = demo_grp)) +
		geom_line()+ geom_point()+ 
		labs(x = 'Number of polls', y = 'Equity weighted distance (m)', color = "Run Type", shape = 'Demographic')+ 
		scale_shape_discrete(labels = demographic_legend_dict) + 
		scale_color_manual(breaks = c('Intersecting', 'Contained'), values = c('red','darkviolet'))
	ggsave(paste0(demo_grp, '_compare_demographic_edes.png'))
}

#makes two plots, one showing the y_ede the other avg distance
#showing how these variables change across the included runs
#Note: This can produce a graph very similar to the one above,
#but the formatting of this one is better for historical analysis,
#while the formatting of the previous is better for many polls

#ACCOMODATES DRIVING DISTANCES

plot_historic_edes <- function(orig_ede, suffix = '', driving_flag = DRIVING_FLAG){	
	
	#set x axis label order
	descriptor_order <- unique(orig_ede$descriptor)

	#select y axis bounds
	all_y_values = c(c(orig_ede$avg_dist), c(orig_ede$y_EDE))
	y_min = min(all_y_values)
	y_max = max(all_y_values)

	#set point size
	#does data contain scaling data
	scale_bool = 'pct_demo_population' %in% names(orig_ede)
	
	#is this driving distance data
	if (driving_flag){
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

#join population data to ede graphs in order to get population scaled graphs
ede_with_pop<- function(config_df_list){
	demo_pop <- config_df_list$precinct_distances[ , .(total_population = sum(demo_pop)), by  = c('descriptor', 'demographic')]
	total_pop <- demo_pop[demographic == 'population', c('descriptor', 'total_population')]
	demo_pop <- merge(demo_pop, total_pop, by = 'descriptor')
	setnames(demo_pop, c('total_population.x', 'total_population.y'), c('total_demo_population', 'total_population'))
	demo_pop[ , pct_demo_population := total_demo_population/ total_population]
	edes_with_pop <- merge(config_df_list$edes, demo_pop, by = c('descriptor', 'demographic'))
	return(edes_with_pop)
}

#compares optimized runs with historical runs having the same number of 
#polls (via plot_historical_edes)

#ACCOMODATES DRIVING DISTANCES
plot_original_optimized <- function(config_ede, orig_ede, suffix = '', driving_flag = DRIVING_FLAG){	
	#select the relevant optimized runs
	orig_num_polls <- unique(orig_ede$num_polls)
	config_num_polls <- unique(config_ede$num_polls)
	optimization_num_polls<- max(intersect(orig_num_polls, config_num_polls))
	optimized_run_dfs <- config_ede[num_polls == optimization_num_polls]
	orig_and_optimal <- rbind(orig_ede, optimized_run_dfs)
	plot_historic_edes(orig_and_optimal, paste0('and_optimal', suffix), driving_flag)

}

#like plot_poll_edes, but plots just the y_edes for the
# population as a whole, and not demographic groups

#DOES NOT ACCOMODATE DRIVING DISTANCES
plot_population_edes <- function(ede_df){	
	ggplot(ede_df[demographic == 'population', ], aes(x =  num_polls, y = y_EDE))+
		geom_line()+ geom_point()+
		labs(x = 'Number of polls', y = 'Equity weighted distance (m)')

	ggsave('population_edes.png')
}

#a plot showing which precincts are used for which number of polls
#also makes a panel of graphs showing which demographics are assigned to each poll
plot_precinct_persistence <- function(precinct_df){
	ggplot(precinct_df[demographic == 'population',
		], aes(x = num_polls, y = id_dest)) +
		geom_point(aes(size = demo_pop)) + 
		labs(x = 'Number of polls', y = 'EV location', size = paste(demographic_legend_dict['population'], 'population'))

	ggsave('precinct_persistence.png')

	ggplot(precinct_df[demographic != 'population',
		], aes(x = num_polls, y = id_dest)) +
		geom_point(aes(size = demo_pop)) + 
		labs(x = 'Number of polls', y = 'EV location', size = 'Population') + facet_wrap(~ demographic) +
		theme(legend.position = c(0.9, 0.2))

	ggsave('precinct_persistence_demographic.png')
}

#make boxplots of the average distances traveled and the y_edes at each run 

#DOES NOT ACCOMODATE DRIVING DISTANCES
plot_boxplots <- function(residence_df){
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

#make histogram of the average distances traveled in the historical and ideal situations 

#DOES NOT ACCOMODATE DRIVING DISTANCES
plot_orig_ideal_hist <- function(orig_residence_df, config_residence_df, ideal_num){
	orig_residence_df <- orig_residence_df[demographic == 'population', ]
	ideal_residence_df <- config_residence_df[demographic == 'population', ][num_polls == ideal_num, ]
	res_pop_orig_and_ideal <- rbind( ideal_residence_df, orig_residence_df)

	#avg_distance
	ggplot(res_pop_orig_and_ideal, aes(x = avg_dist, fill = descriptor)) + 
		geom_histogram(aes(weight = demo_pop), position = "dodge", alpha = 0.8)+
		labs(x = 'Average distance traveled to poll (m)', y = 'Number of people', fill = 'Optimization Run') 
		ggsave('avg_dist_distribution_hist.png')

}

#####CAUTION: USED FOR DELIVERY, BUT EXPERIMENTAL######

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

#####STOP HERE######
#####REGRESSION FUNCTIONS AFTER THIS MAY NOT WORK AS DESIRED######

#######
#make regression
#######

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



