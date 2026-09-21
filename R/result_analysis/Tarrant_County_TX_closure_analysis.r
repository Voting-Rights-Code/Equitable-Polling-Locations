library(data.table)
library(interactions)
library(ggplot2)
library(here)
library(gargle)
options(gargle_oauth_email = TRUE)

setwd(here())

# For uploading outputs to Google Cloud Storage
source('R/result_analysis/utility_functions/storage.R')
# For shared plot styling (theme_tableau, title/subtitle auto-wrapping)
source('R/result_analysis/utility_functions/tableau_theme.R')
# For define_connection(), needed by the county config file sourced below
source('R/result_analysis/utility_functions/load_config_data.R')
# For to load data correctly either from csv or the database
source('R/result_analysis/utility_functions/graph_functions.R')
# Get config constants for Tarrant County, TX, including the Google Cloud Storage bucket name
source('R/result_analysis/Basic_analysis_configs/Tarrant_County_original_and_fair_2026.r')


#########Set up constants and folders ##################3
# Reassign the config's own analysis name 
CLOUD_STORAGE_ANALYSIS_NAME <- 'Tarrant_County_TX_exploration'

#this should only be run after Basic_analysis.r has been run for
#Tarrant_County_original_and_fair_capacity_2.r
required_folders <- file.path(here(), 'result_analysis_outputs',
  c('Tarrant_County_TX_original_configs_capacity_2', 'Tarrant_County_TX_fair_capacity_2'))
missing_folders <- required_folders[!file.exists(required_folders)]
if (length(missing_folders) > 0){
  stop(paste0(paste(missing_folders, collapse = ', '),
    ' does not exist. Run Basic_analysis.r for Tarrant_County_original_and_fair_capacity_2.r first.'))
}

######## load data ############
#load data, whether from csv or database
orig_config_dt <- load_config_data(LOCATION, ORIG_CONFIG_FOLDER)
orig_output_df_list <- read_result_data(orig_config_dt, field_of_interest = ORIG_FIELD_OF_INTEREST, descriptor_dict = DESCRIPTOR_DICT_ORIG)

potential_config_dt <- load_config_data(LOCATION, POTENTIAL_CONFIG_FOLDER)
potential_output_df_list <- read_result_data(potential_config_dt, field_of_interest = POTENTIAL_FIELD_OF_INTEREST, 
descriptor_dict = DESCRIPTOR_DICT_POTENTIAL)


#read in 2024, and 2025 and 2026 historical precinct data, as well as the optimal assignments and proposed 2026 assignments
precinct_dt <- orig_output_df_list$precinct_distances
dt_2024     <- precinct_dt[descriptor == '2024']
dt_2025     <- precinct_dt[descriptor == '2025']
dt_2026     <- precinct_dt[descriptor == '2026']    
dt_2026prop <- precinct_dt[descriptor == 'proposed']
dt_optimal_215 <- potential_output_df_list$precinct_distances[descriptor == '215_open']


######## sort dropped polls ############

#separate out demographic numbers into columns
#Note, this loses the distance data
dt_2024_pop <- dcast(dt_2024, id_dest ~ demographic, value.var = 'demo_pop' )
dt_2025_pop <- dcast(dt_2025, id_dest ~ demographic, value.var = 'demo_pop' )


#add in flags for when a polling location is dropped
polls_2025 = unique(dt_2025$id_dest)
polls_2026 = unique(dt_2026$id_dest)
polls_2026prop = unique(dt_2026prop$id_dest)
polls_optimal  = unique(dt_optimal_215$id_dest)

dt_pop_polls_2024 <- dt_2024_pop[ , dropped_2025 := TRUE
                ][id_dest %in% polls_2025, dropped_2025 := FALSE
                ][ , dropped_2026 := TRUE][id_dest %in% polls_2026, dropped_2026 := FALSE
                ][ , dropped_optimal_215 := TRUE
                ][id_dest %in% polls_optimal, dropped_optimal_215 := FALSE
                ][ , dropped_2026prop := TRUE
                ][id_dest %in% polls_2026prop, dropped_2026prop := FALSE
                ]

dt_pop_polls_2025 <- dt_2025_pop[ , dropped_2026 := TRUE
                ][id_dest %in% polls_2026, dropped_2026 := FALSE
                ][ , dropped_2026prop := TRUE
                ][id_dest %in% polls_2026prop, dropped_2026prop := FALSE
                ]

#csv of precincts kept by year and population assigned to each.
combined <- rbind(dt_2024, dt_2025, dt_2026, dt_2026prop, fill = TRUE)
precinct_persistence_demographics <- dcast(combined, id_dest + demographic ~ descriptor, value.var = 'demo_pop')
precinct_persistence_demographics[ , pct_change_24_to_26 := as.character(round((`2026`-`2024`)/`2024`, 2))
                ][is.na(`2024`), pct_change_24_to_26 := 'New']

######## run models ############

#create and plot the interaction of Latine and White populations on the probability
#of poll closures.
plot_white_latine_interation <- function(dt, dropped_col, base_year, target_run, model_type){
  #set up model title arguments based on model_type
  if (model_type == 'lpm'){
    model <- lm
    family_arg <- NULL
    model_label <- "LPM"
    } else if (model_type == 'logit'){
    model <- glm
    family_arg <- binomial(link = "logit")
    model_label <- "Logistic"
  } else {
    stop("model_type must be either 'lpm' or 'logit'")
  }

  #set up title labels based on target_run
  target_label <- if (target_run == "optimal") "Optimal Race-Blind" else target_run

  latine_white_interaction <- model(as.formula(paste0(dropped_col, " ~ hispanic + white + (hispanic):(white)")), dt, family = family_arg)
  plot <- interact_plot(latine_white_interaction, hispanic, white,
    main.title = paste0("Effect of Latine Population on Probability of ", target_label, " Poll Closures (", model_label, ")"),
     y.label = "Probability of Poll Closure", x.label = "Latine Population",
    legend.main = "White Population") + ylim(0, 1) + theme_tableau() + labs(subtitle = paste("Comparison to", base_year))
  file_name <- paste0("latine_white_interaction_", model_type, "_", base_year, "_", target_run, ".png")
  add_graph_to_graph_file_manifest(file_name)
  ggsave(file_name)
}

###Historic runs
setwd(file.path(here(), "result_analysis_outputs/Tarrant_County_TX_original_configs_capacity_2"))
#plot regressions
plot_white_latine_interation(dt_pop_polls_2024, "dropped_2025", "2024", "2025", "lpm")
plot_white_latine_interation(dt_pop_polls_2024, "dropped_2026", "2024", "2026", "lpm")
plot_white_latine_interation(dt_pop_polls_2025, "dropped_2026", "2025", "2026", "lpm")
plot_white_latine_interation(dt_pop_polls_2024, "dropped_2026prop", "2024", "2026prop", "lpm")
plot_white_latine_interation(dt_pop_polls_2025, "dropped_2026prop", "2025", "2026prop", "lpm")

plot_white_latine_interation(dt_pop_polls_2024, "dropped_2025", "2024", "2025", "logit")
plot_white_latine_interation(dt_pop_polls_2024, "dropped_2026", "2024", "2026", "logit")
plot_white_latine_interation(dt_pop_polls_2025, "dropped_2026", "2025", "2026", "logit")
plot_white_latine_interation(dt_pop_polls_2024, "dropped_2026prop", "2024", "2026prop", "logit")
plot_white_latine_interation(dt_pop_polls_2025, "dropped_2026prop", "2025", "2026prop", "logit")

#precinct persistence data
add_graph_to_graph_file_manifest('precinct_demographics_by_year.csv')
fwrite(precinct_persistence_demographics, 'precinct_demographics_by_year.csv')


###Optimized runs
setwd(file.path(here(), "result_analysis_outputs/Tarrant_County_TX_fair_capacity_2"))

#plot regressions
plot_white_latine_interation(dt_pop_polls_2024, "dropped_optimal_215", "2024", "optimal", "lpm")
plot_white_latine_interation(dt_pop_polls_2024, "dropped_optimal_215", "2024", "optimal", "logit")


upload_graph_files_to_cloud_storage()