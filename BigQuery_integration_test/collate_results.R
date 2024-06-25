#setwd("BigQuery_integration_test")
library(yaml)

## ==== Define functions ====

append_fields <- function(config_names, locations, result_dir, config_set, out_type){
  data.list <- mapply(
    function(config_name, location){
      
      dir <- paste0(
        result_dir,
        "/",
        config_set,
        ".",
        config_name,
        "_",
        out_type,
        ".csv"
      )
      
      # Read in the data, and add a "config_name" field that will vary within the output
      data <- read.csv(dir)
      data$config_name <- config_name
      
      # Append location and config_set variables that will remain constant within the output
      data$location <- location
      data$config_set <- config_set
      
      return(data)
    },
    config_name = config_names, location = locations, SIMPLIFY = FALSE
  )
  
  names(data.list) <- config_names
  
  return(data.list)
}

collate_outs <- function(config_names, locations, result_dir, config_set, out_type){
  data.list <- append_fields(
    config_names = config_names, 
    locations = locations, 
    result_dir = result_dir, 
    config_set = config_set,
    out_type = out_type
  )
  data.df <- do.call(rbind, data.list)
  rownames(data.df) <- NULL
  
  # Replace "." (not allowed) with "_" in column names
  names(data.df) <- gsub(".", "_", names(data.df), fixed = TRUE)
  
  return(data.df)
}

collate_configs <- function(config_set, config_dir){
  # Read in all YAML files found in the directory config_dir
  all_files <- list.files(config_dir)
  yaml_files <- grep(".yaml", all_files, fixed = TRUE, value = TRUE)
  if(length(yaml_files) == 0) stop("No YAML files found")
  yaml_filepaths <- paste0(config_dir, "/", yaml_files)
  yaml.list <- lapply(yaml_filepaths, read_yaml)
  
  # Combine into an array
  yaml.array <- do.call(rbind, yaml.list)
  yaml.df <- data.frame(yaml.array)
  
  # Convert non-list columns to atomics
  atomic_col_names <- c("location", "beta", "time_limit", "capacity", "precincts_open",
                        "max_min_mult", "maxpctnew", "minpctold")
  yaml.df[, atomic_col_names] <- lapply(yaml.df[, atomic_col_names], simplify2array)
  null_list_names <- atomic_col_names[sapply(yaml.df[, atomic_col_names], is.list)]
  if(length(null_list_names) > 0) yaml.df[, null_list_names] <- NA
  
  # Add config name and config set columns
  yaml.df$config_name <- gsub(".yaml", "", yaml_files, fixed = TRUE)
  yaml.df$config_set <- config_set
  
  # Add placeholder columns
  yaml.df$commit_hash <- NA
  yaml.df$run_time <- NA
  
  # Return
  return(yaml.df)
}

literalize_list <- function(col, is.char = TRUE){
  rec <- sapply(col, function(onerow){
    atomic <- onerow
    if(is.char) atomic <- paste0("'", onerow, "'")
    inner <- paste(atomic, collapse = ", ")
    outer <- paste0("[", inner, "]")
    
    return(outer)
  })
  
  return(rec)
}


## ==== Test ====
# 'Incomplete final line' warning are expected below and seem ignorablew

# --- Tests ---
# Read in York and Berkeley configs
york_configs.df <- collate_configs(config_set = "York_SC_original_configs", config_dir = "../York_SC_original_configs")
berkeley_configs.df <- collate_configs(config_set = "Berkeley_SC_original_configs", config_dir = "../Berkeley_SC_original_configs")

# Read in Dekalb configs to validate that we can handle with an array of years per config
dekalb_test_configs.df <- collate_configs(config_set = "Dekalb_GA_no_bg_school_configs", config_dir = "../Dekalb_GA_no_bg_school_configs")


## ==== Run ====

# --- Set parameters ----
# Set directories
config_set <- "York_SC_original_configs"
config_dir <- "../York_SC_original_configs"
result_dir <- "../York_SC_results"
out_dir <- paste0(config_set, "_collated")

# --- Read in and collate YAML file ----
# Collate config files, and get info from them
configs.df <- collate_configs(config_set = config_set, config_dir = config_dir)
locations <- simplify2array(configs.df$location)
config_names <- simplify2array(configs.df$config_name)

# --- Collate output files ---
out_types <- c("result", "edes", "precinct_distances", "residence_distances")
names(out_types) <- out_types
outs.df <- lapply(out_types, function(out_type){
  collated <- collate_outs(
    config_names = config_names, 
    locations = locations, 
    result_dir = result_dir, 
    config_set = config_set,
    out_type = out_type
  )
})
outs.df$result$X <- NULL
outs.df$result$county <- NULL

# --- Write to CSV ---
if(!dir.exists(out_dir)) dir.create(out_dir)
lapply(out_types, function(out_type){
  write.csv(
    outs.df[[out_type]], 
    file = paste0(out_dir, "/", config_set, "_", out_type, ".csv"),
    row.names = FALSE
    
  )
})

configs_literal.df <- configs.df
configs_literal.df$year <- literalize_list(configs_literal.df$year, is.char = FALSE)
configs_literal.df$bad_types <- literalize_list(configs_literal.df$bad_types, is.char = TRUE)
write.csv(
  configs_literal.df, 
  file = paste0(out_dir, "/", config_set, "_configs.csv"),
  row.names = FALSE
)

