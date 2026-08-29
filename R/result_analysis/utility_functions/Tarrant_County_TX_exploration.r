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

STORAGE_BUCKET <- 'equitable-polling-analysis'
CLOUD_STORAGE_ANALYSIS_NAME <- 'Tarrant_County_TX_exploration'


#read in 2024, and 2025 and 2026 historical precinct data, as well as the optimal assignments
dt_2024 <- fread('datasets/results/Tarrant_County_TX_results/Tarrant_County_TX_original_configs_capacity_2.Tarrant_County_TX_year_2024_precinct_distances.csv')

dt_2025 <- fread('datasets/results/Tarrant_County_TX_results/Tarrant_County_TX_original_configs_capacity_2.Tarrant_County_TX_year_2025_precinct_distances.csv')

dt_2026 <- fread('datasets/results/Tarrant_County_TX_results/Tarrant_County_TX_original_configs_capacity_2.Tarrant_County_TX_year_2026_precinct_distances.csv')

dt_optimal_215 <- fread('datasets/results/Tarrant_County_TX_results/Tarrant_County_TX_fair_capacity_2.Tarrant_County_TX_precincts_open_215_precinct_distances.csv')

#separate out demographic numbers into columns
#Note, this loses the distance data
dt_2024_pop <- dcast(dt_2024, id_dest ~ demographic, value.var = 'demo_pop' )
dt_2025_pop <- dcast(dt_2025, id_dest ~ demographic, value.var = 'demo_pop' )


#add in flags for when a polling location is dropped
polls_2025 = unique(dt_2025$id_dest)
polls_2026 = unique(dt_2026$id_dest)
polls_optimal  = unique(dt_optimal_215$id_dest)

dt_pop_polls_2024 <- dt_2024_pop[ , dropped_2025 := TRUE
                ][id_dest %in% polls_2025, dropped_2025 := FALSE
                ][ , dropped_2026 := TRUE][id_dest %in% polls_2026, dropped_2026 := FALSE
                ][ , dropped_optimal_215 := TRUE][id_dest %in% polls_optimal, dropped_optimal_215 := FALSE]

dt_pop_polls_2025 <- dt_2025_pop[ , dropped_2026 := TRUE
                ][id_dest %in% polls_2026, dropped_2026 := FALSE
                ]

#run models

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
plot_white_latine_interation(dt_pop_polls_2024, "dropped_2025", "2024", "2025", "lpm")
plot_white_latine_interation(dt_pop_polls_2024, "dropped_2026", "2024", "2026", "lpm")
plot_white_latine_interation(dt_pop_polls_2025, "dropped_2026", "2025", "2026", "lpm")
plot_white_latine_interation(dt_pop_polls_2024, "dropped_2025", "2024", "2025", "logit")
plot_white_latine_interation(dt_pop_polls_2024, "dropped_2026", "2024", "2026", "logit")
plot_white_latine_interation(dt_pop_polls_2024, "dropped_2026", "2025", "2026", "logit")

###Optimized runs
setwd(file.path(here(), "result_analysis_outputs/Tarrant_County_TX_fair_capacity_2"))

plot_white_latine_interation(dt_pop_polls_2024, "dropped_optimal_215", "2024", "optimal", "lpm")
plot_white_latine_interation(dt_pop_polls_2024, "dropped_optimal_215", "2024", "optimal", "logit")


upload_graph_files_to_cloud_storage()