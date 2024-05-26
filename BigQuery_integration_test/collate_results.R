#setwd("BigQuery_integration_test")

## ==== Define functions ====

append_fields <- function(config_name, config_dir, result_dir, location, file, years){
  data.list <- lapply(
    years, function(year){
      
      dir <- paste0(
        "../",
        result_dir,
        "/",
        config_dir,
        ".",
        config_name,
        "_",
        year,
        "_",
        file,
        ".csv"
      )
      
      data <- read.csv(dir)
      data$config <- paste0(config_name, "_", year)
      data$location <- location
      
      return(data)
    }
  )
  
  names(data.list) <- paste0(config_name, "_", years)
  
  return(data.list)
}

collate_years <- function(config_name, config_dir, result_dir, location, file, years){
  data.list <- append_fields(
    config_name = config_name, 
    config_dir = config_dir, 
    result_dir = result_dir, 
    location = location, 
    file = "edes", 
    years = years
  )
  
  data.df <- do.call(rbind, data.list)
  rownames(data.df) <- NULL
  return(data.df)
}

## ==== Run ====

# ---- York ----
config_name <- "York_config_original"
config_dir <- "York_SC_original_configs"
result_dir <- "York_SC_results"
location <- "York_SC"

years <- c(2014, 2016, 2018, 2020, 2022)

files <- c("result", "edes", "precinct_distances", "residence_distances")
names(files) <- files

York_collated <- lapply(files, function(file){
  collated <- collate_years(
    config_name = config_name, 
    config_dir = config_dir, 
    result_dir = result_dir, 
    location = location, 
    file = file, 
    years = years
  )
})
lapply(files, function(file){
  write.csv(York_collated[[file]], file = paste0(result_dir, "_collated_2/", file, ".csv"))
})

# ---- Berkeley ----
config_name <- "Berkeley_config_original"
config_dir <- "Berkeley_SC_original_configs"
result_dir <- "Berkeley_SC_results"
location <- "Berkeley_SC"

years <- c(2014, 2016, 2018, 2020, 2022)

files <- c("result", "edes", "precinct_distances", "residence_distances")
names(files) <- files

Berkeley_appended.df <- lapply(files, function(file){
  append_fields(
    config_name = config_name, 
    config_dir = config_dir, 
    result_dir = result_dir, 
    location = location, 
    file = file, 
    years = years
  )
})

write.csv(
  Berkeley_appended.df$result$Berkeley_config_original_2014, 
  file = "Berkeley_SC_original_configs.Berkeley_config_original_2014_result.csv"
)

write.csv(
  Berkeley_appended.df$edes$Berkeley_config_original_2014, 
  file = "Berkeley_SC_original_configs.Berkeley_config_original_2014_edes.csv"
)

write.csv(
  Berkeley_appended.df$precinct_distances$Berkeley_config_original_2014, 
  file = "Berkeley_SC_original_configs.Berkeley_config_original_2014_precinct_distances.csv"
)

write.csv(
  Berkeley_appended.df$residence_distances$Berkeley_config_original_2014, 
  file = "Berkeley_SC_original_configs.Berkeley_config_original_2014_residence_distances.csv"
)



