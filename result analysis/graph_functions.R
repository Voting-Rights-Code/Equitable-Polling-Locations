library(data.table)
library(ggplot2)
library(stringr)
library(here)
library(plotly)
library(DBI)
library(bigrquery)

#######
#Check that location and folders valid
#######
check_location_valid <- function(location, config_folder){
	#raise error if config folder does contain a file with location in the file name
	county = gsub('.{3}$','',location)
	location_in_folder =  sapply(county, function(x)any(grepl(x, list.files(config_folder))))
	if (!all(location_in_folder)){
		bad_locations = paste(location[!location_in_folder], collapse = ', ')
    	stop(paste('Given config folder does not contain data for the following location(s):', bad_locations))
}
}

check_config_folder_valid <- function(config_folder){
	#raise error if config folder not a directory
	if (!dir.exists(config_folder)){
    	stop('Config folder does not exist')
}
}

######
#Functions to read in results
#Two types to analysis: historical (see CLC work); placement (see FFA work)
######
combine_results<- function(config_folder, result_type, analysis_type = 'placement'){
	if (analysis_type == 'historical'){
		return(combine_results_multi_county_historical(config_folder, result_type))}
	else if (analysis_type == 'placement'){
		return(combine_results_placement(config_folder, result_type))}
	else{
		stop("Incorrect analysis_type provided")
	}
}


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
		descriptor <- mapply(function(x,y){paste(x, y, sep='_')}, location, years)} #county and year
	else if (analysis_type == 'placement'){
		result_folder <-paste(location, 'results/', sep = '_')
		files <- list.files(result_folder)
		files <- files[grepl(config_folder, files) &grepl(result_type, files)]
		file_path <- paste0(result_folder, files)
		
		#pull number of polls data from the file names
		num_polls <-  gsub('.*?([0-9]+).*', '\\1', files)
		descriptor <- sapply(num_polls, function(x){paste('Optimized', num_polls, 'polls', sep='_')})} #number of polls
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

construct_results_query <- function(config_name = NULL, config_set = NULL, location = NULL, table){
  query_params <- list(config_name = config_name, config_set = config_set, location = location)
  query_params <- query_params[!sapply(query_params, is.null)]
  if(length(query_params) == 0) stop("No valid parameters passed to get_results_bigquery")
  
  query_params_str <- paste0(
    sapply(names(query_params), function(param_name){
      rhs_str <- paste0("(", paste0("'", query_params[[param_name]], "'", collapse = ", "), ")")
      lhs_str <- paste0(param_name, " IN ")
      param_str <- paste0(lhs_str, rhs_str)
    }),
    collapse = " AND "
  )
  
  query_base_str <- paste0(
    "SELECT *
    FROM
    polling.",
    table,
    "_extra WHERE"
  )
  
  query_str <- paste(query_base_str, " ", query_params_str)
  
  return(query_str)
}

get_table_bigquery <- function(config_name = NULL, config_set = NULL, location = NULL, tables, analysis_type = 'placement'){
  #read in and format one table for a given combination of parameters
  #at least one of config_name, config_set, location, and (deprecated) config_folder

  con <- dbConnect(
    bigrquery::bigquery(),
    project = project,
    dataset = dataset
  )
  
  out <- lapply(tables, function(table){
    sql <- construct_results_query(config_name = config_name, config_set = config_set, location = location, table = table)
    data <- dbGetQuery(con, sql)
  })
  
  return(out)  
}

query_result_data <-  function(config_name = NULL, config_set = NULL, location = NULL, config_folder = NULL, analysis_type = "placement"){
  #read in and format all the results data for a given combination of parameters
  #at least one of config_name, config_set, location, and (deprecated) config_folder
  #config_folder: string (deprecated in favor of config_set); a synonym for config_set
  #analysis_type: string (historical, placement)
  #returns: list(ede_df, precinct_df, residence_df, result_df), with appended "descriptor" fields
  
  tables <- c("edes", "result", "precinct_distances", "residence_distances")
  if(missing(config_set) & !missing(config_folder)){
    config_set <- config_folder
    warning("config_folder parameter was specified; please use config_set instead")
  }
  
  data <- get_table_bigquery(config_name = config_name, config_set = config_set, location = location, tables = tables)
  names(data) <- tables
  
  if(analysis_type == "historical"){
    data <- lapply(data, function(df){
      df$descriptor <- paste(df$location, "_", df$year)
    })
  } else if(analysis_type == "placement"){
    data <- lapply(data, function(df){
      df$descriptor <- paste("Optimized_", df$precincts_open, "_polls")
    })
  } else{
    stop("Incorrect analysis_type provided. Analysis type must be historical or placement")}
  
  #label descriptors with polls and residences
  num_polls <- data$precinct_distances[ , .(num_polls = .N/6), by = descriptor]
  num_residences <- data$residence_distances[ , .(num_residences = .N/6), by = descriptor]
  nums_to_join <- merge(num_polls, num_residences, all = T)
  
  ede_df <- merge(data$edes, nums_to_join, all.x = T)
  precinct_df <- merge(data$precinct_distances, nums_to_join, all.x = T)
  residence_df <- merge(data$residence_distances, nums_to_join, all.x = T)
  result_df <- merge(data$result, nums_to_join, all.x = T)
  
  return(list(ede_df, precinct_df, residence_df, result_df))
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
#dictionary for labels
#######

demographic_legend_dict <- c(
	'asian' = 'Asian (not PI)', 
	'black' = 'African American', 
	'white' = 'White', 
	'hispanic' = 'Latine',
	'native' = 'First Nations',
	'population' = 'Total Population')

#######
#constants for database queries 
#######

project <- "voting-rights-storage-test"
dataset <- "polling"

#######
#functions to make plots
#######

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


#makes two plots, one showing the y_ede the other avg distance
#showing how these variables change across the included runs
#Note: This can produce a graph very similar to the one above,
#but the formatting of this one is better for historical analysis,
#while the formatting of the previous is better for many polls

#ACCOMODATES DRIVING DISTANCES

plot_historic_edes <- function(orig_ede, suffix = ''){	
	
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

#join population data to ede graphs in order to get population scaled graphs
ede_with_pop<- function(config_df_list){
	demo_pop <- config_df_list[[2]][ , .(total_population = sum(demo_pop)), by  = c('descriptor', 'demographic')]
	total_pop <- demo_pop[demographic == 'population', c('descriptor', 'total_population')]
	demo_pop <- merge(demo_pop, total_pop, by = 'descriptor')
	setnames(demo_pop, c('total_population.x', 'total_population.y'), c('total_demo_population', 'total_population'))
	demo_pop[ , pct_demo_population := total_demo_population/ total_population]
	edes_with_pop <- merge(config_df_list[[1]], demo_pop, by = c('descriptor', 'demographic'))
	return(edes_with_pop)
}

#compares optimized runs with historical runs having the same number of 
#polls (via plot_historical_edes)

#ACCOMODATES DRIVING DISTANCES
plot_original_optimized <- function(config_ede, orig_ede, suffix = ''){	
	#select the relevant optimized runs
	orig_num_polls <- unique(orig_ede$num_polls)
	optimized_run_dfs <- config_ede[num_polls %in% orig_num_polls]
	orig_and_optimal <- rbind(orig_ede, optimized_run_dfs)
	plot_historic_edes(orig_and_optimal, paste0('and_optimal', suffix))
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
		labs(x = 'Average distance traveled to poll (m)', y = 'Number of people') +
		scale_fill_manual(values=c("red", "blue", "green"), name = "Optimization run ")
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



