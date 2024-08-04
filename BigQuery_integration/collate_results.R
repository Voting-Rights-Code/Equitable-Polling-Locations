# Greenville - no YAML files found 
# Fix issue with Berkeley SC config - "pyarrow.lib.ArrowInvalid: Float value 1 was truncated converting to int64"

library(yaml)

# Set working directory to BigQuery_integration directory
if((strsplit(getwd(), "/", fixed = TRUE)[[1]][length(strsplit(getwd(), "/", fixed = TRUE)[[1]])]) != "BigQuery_integration"){
  setwd("BigQuery_integration")
}


## ==== Set key parameters and run ====

config_folders_rec <- read.csv("filemaps.csv")

loc_changes <- list(
  c(old = "Berkeley_SC", new = "Berkeley_County_SC"),
  c(old = "Cobb_GA", new = "Cobb_County_GA"),
  c(old = "Dekalb_GA", new = "Dekalb_County_GA"),
  c(old = "Greenville_SC", new = "Greenville_County_SC"),
  c(old = "Gwinett_GA", new = "Gwinett_County_GA"),
  c(old = "Lexington_SC", new = "Lexington_County_SC"),
  c(old = "Richland_SC", new = "Richland_County_SC"),
  c(old = "York_SC", new = "York_County_SC")
)


## ==== Define functions ====

# Add config_name and config_Set fields to an output file
append_fields <- function(config_names, result_dir, config_set, out_type){
  data.list <- lapply(
    config_names,
    function(config_name){
      
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
      if(file.exists(dir)){
        data <- read.csv(dir)
        data$config_name <- config_name
        
        # Append config_set variables that will remain constant within the output
        data$config_set <- config_set
      } else data <- NULL
      
      return(data)
    }
  )
  
  names(data.list) <- config_names
  
  return(data.list)
}

# Collate output data for one type of output (results, edes, etc)
# Across multiple model runs
collate_outs <- function(config_names, result_dir, config_set, out_type){
  data.list <- append_fields(
    config_names = config_names, 
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

# Collate output data for multiple configs
collate_configs <- function(config_set, config_dir, loc_changes){
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
  
  # Standardize capitalization on "city" to lowercase
  yaml.df$location <- gsub("City", "city", yaml.df$location)
  # Change naming convention for older configs
  if(!missing(loc_changes)){
    for(loc_change in loc_changes){
      yaml.df$location <- gsub(loc_change["old"], loc_change["new"], yaml.df$location)
    }
  }
  
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

collate_runs <- function(config_set, config_dir, result_dir, out_dir, loc_changes){
    # --- Read in and collate YAML file ----
    # Collate config files, and get info from them
    configs.df <- collate_configs(config_set = config_set, config_dir = config_dir, loc_changes = loc_changes)
    config_names <- simplify2array(configs.df$config_name)
    
    # --- Collate output files ---
    out_types <- c("result", "edes", "precinct_distances", "residence_distances")
    names(out_types) <- out_types
    outs.df <- lapply(out_types, function(out_type){
      collated <- collate_outs(
        config_names = config_names, 
        result_dir = result_dir, 
        config_set = config_set,
        out_type = out_type
      )
    })
    outs.df$result$X <- NULL
    outs.df$result$county <- NULL
    
    outs.df$result$id_orig <- as.character((outs.df$result$id_orig))
    outs.df$residence_distances$id_orig <- as.character((outs.df$residence_distances$id_orig))
  
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
    if(!is.null(configs_literal.df$driving_distance_file_path)) configs_literal.df$driving_distance_file_path <- as.character(configs_literal.df$driving_distance_file_path)
    
    write.csv(
      configs_literal.df, 
      file = paste0(out_dir, "/", config_set, "_configs.csv"),
      row.names = FALSE
    )
}
  
  
## ==== Test ====
# --- Tests of low-level functions ---
# Read in York and Berkeley configs
york_configs.df <- collate_configs(config_set = "York_SC_original_configs", config_dir = "../York_SC_original_configs")
berkeley_configs.df <- collate_configs(config_set = "Berkeley_SC_original_configs", config_dir = "../Berkeley_SC_original_configs")

# Read in Dekalb configs to validate that we can handle with an array of years per config
dekalb_test_configs.df <- collate_configs(config_set = "Dekalb_GA_no_bg_school_configs", config_dir = "../Dekalb_GA_no_bg_school_configs")

# --- Test run of collate_run ---
# Set directories
# collate_runs(
#   config_set = "Cobb_GA_no_bg_school_configs",
#   config_dir = "../Cobb_GA_no_bg_school_configs",
#   result_dir = "../Cobb_GA_results",
#   out_dir = "Cobb_GA_no_bg_school_configs_collated"
# )
# 
# collate_runs(
#   config_set = "York_SC_original_configs",
#   config_dir = "../York_SC_original_configs",
#   result_dir = "../York_SC_results",
#   out_dir = "York_SC_original_configs_collated"
# )


collate_runs(
  config_set = "DeKalb_GA_no_bg_school_configs",
  config_dir = "../DeKalb_GA_no_bg_school_configs",
  result_dir = "../DeKalb_GA_results",
  out_dir = "DeKalb_GA_no_bg_school_collated"
)

collate_runs(
  config_set = "Engage_VA_2024_original_configs",
  config_dir = "../Engage_VA_2024_original_configs",
  result_dir = "../Engage_VA_results",
  out_dir = "Engage_VA_original_collated"
)

collate_runs(
  config_set = "Engage_VA_2024_driving_configs",
  config_dir = "../Engage_VA_2024_driving_configs",
  result_dir = "../Engage_VA_results",
  out_dir = "Engage_VA_2024_driving"
)




## ==== Run ==== 

mapply(
  collate_runs,
  config_set = config_folders_rec$config_set,
  config_dir = config_folders_rec$config_dir,
  result_dir = config_folders_rec$result_dir,
  out_dir = config_folders_rec$out_dir,
  MoreArgs = list(loc_changes = loc_changes)
)

