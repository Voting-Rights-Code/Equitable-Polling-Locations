library(data.table)
library(ggplot2)
library(stringr)
library(here)

source('R/result_analysis/utility_functions/load_config_data.R')
source('R/result_analysis/utility_functions/storage.R')

#########
#Create dataframes for regressions and graphs
#1. combine result data with block area data to get population density and related measures
#2. take density data and aggregate key columns up to the block level
#########

get_density_data<-function(location, result_df){
	#if result_df is NULL, and HISTORIC_FLAG return NULL
	if(check_historic_flag(result_df)){
		return(NULL)
	}

	#get block area data:
    #pull .shp files from tiger data, 
    #extract GEOID20, Land area and water eara for each block
	map_folders <- paste0(here(),'/datasets/census/tiger/', location, '/')
	map_files <- paste0(map_folders, list.files(map_folders)[endsWith(list.files(map_folders), 'tabblock20.shp')])
	map_data<- lapply(map_files, st_read)

	block_areas <- lapply(map_data, function(x){x[, c('GEOID20', 'ALAND20', 'AWATER20')]})
	if (length(block_areas)> 1){
		block_areas <- do.call(rbind, block_areas)
	}

    #calculate density data for regression
	#merge block area data with result data
    #calculate population density (people/ km^2), average distance, pct white, pct black, 
    #population density quantile, and a fuzzy distance (max(distance_m, 100))
	regression_data <- merge(result_df, block_areas, by.x = 'id_orig', by.y = 'GEOID20', all.x = T)

	regression_data[ , `:=`(area = ALAND20 + AWATER20, pop_density_km = 1e6 *population/(ALAND20 + AWATER20), pct_white= 100 * white/population, pct_black = 100 *black/population,  avg_distance = weighted_dist/population)][ , density_pctile := rank(pop_density_km)/length(pop_density_km)][ , fuzzy_dist :=distance_m][fuzzy_dist <100, fuzzy_dist := 100]
	return(regression_data)
}

bg_data <- function(density_data){
    #take density data and aggregate key columns up to the block level

	#if density_data is NULL, and HISTORIC_FLAG return NULL
	if(check_historic_flag(density_data)){
		return(NULL)
	}
    
    #Melt density data to make a demographic population column
    density_data_long <- melt(density_data, id.vars = c('id_orig', 'descriptor', 'pop_density_km','avg_distance', 'area'), measure.vars = c("population", "hispanic","non_hispanic", "white", "black", "native", "asian", "pacific_islander", "other"), value.name ='demo_pop' , variable.name = "demographic")
    
    #create a block level demographic weighted distance and a block group id column
    density_data_long[ , demo_weighted_dist := demo_pop * avg_distance
                    ][, id_bg := gsub('.{3}$', '', density_data_long$id_orig)]
    
    #aggregate up to the block group level
    bg_result_df <- density_data_long[ , .(demo_pop = sum(demo_pop), area= sum(area),
									demo_weighted_dist = sum(demo_weighted_dist)),  by=list(id_bg, descriptor, demographic)
								][ , demo_avg_dist := demo_weighted_dist/demo_pop]

    #calculate the block group level population density and the z-score by descriptor and merge back in         
    bg_pop_density <- bg_result_df[demographic == 'population',
                     ][, pop_density_km := 1e6 *demo_pop/area][ , z_score_log_density := scale(log(pop_density_km))]
    bg_result_df<- merge(bg_result_df, bg_pop_density[ , .(id_bg, pop_density_km, z_score_log_density)], by = c('id_bg', 'descriptor'))

    return(bg_result_df)
}

bg_level_naive_regression <- function(regression_data, location = LOCATION){
	trimmed <- regression_data[abs(z_score_log_density)<4, ]
	distance_model <- trimmed[, as.list(coef(lm(log(demo_avg_dist) ~ log(pop_density_km)),  weights = demo_pop )), by = c('descriptor', 'demographic')]
    setnames(distance_model, c('(Intercept)', 'log(pop_density_km)'), c('intercept', 'density_coef'))
	csv_file_path = paste0(location, '_distance_model.csv')
	add_graph_to_graph_file_manifest(csv_file_path)
	fwrite(distance_model, csv_file_path)
	return(distance_model)
}


##############SCRATCH. USED FOR CLC DELIVERY BUT NOT USEFUL#######


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

		graph_file_path = paste0("Pred_dist_at_",  names, ".png")
		add_graph_to_graph_file_manifest(graph_file_path)
		ggsave(graph_file_path)
	}

	good_names <- gsub('%', '', names(pop_density_quantile), fixed = T)
	mapply(function(pctile, pctile_name){plot_pctile_pred(pctile, pctile_name)}, pop_density_quantile, good_names)
}

plot_distance_by_density_black <- function(data, this_descriptor){
	ggplot(data[descriptor == this_descriptor, ], aes(x= pct_black, y = density_pctile)) +
	geom_point(aes(color = distance_m, size = population)) +
	scale_color_viridis_c(limits = c(color_bounds[[1]], color_bounds[[2]]), name = "Distance to poll (m)") + xlim(c(0, 100)) + ylim(c(0,1)) + ggtitle('Distance to poll by Pct Black and Population Density Percentile')

	graph_file_path = paste0(this_descriptor, '_dist_by_density_black.png')
	add_graph_to_graph_file_manifest(graph_file_path)
	ggsave(graph_file_path)
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



