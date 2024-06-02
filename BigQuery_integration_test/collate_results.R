setwd("BigQuery_integration_test")

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
out_dir <- paste0(result_dir, "_collated_v2")

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
if(!dir.exists(out_dir)) dir.create(out_dir)
lapply(files, function(file){
  write.csv(
    York_collated[[file]], 
    file = paste0(our_dir, "/", file, ".csv"),
    row.names = FALSE
  )
})

# ---- Berkeley ----
config_name <- "Berkeley_config_original"
config_dir <- "Berkeley_SC_original_configs"
result_dir <- "Berkeley_SC_results"
location <- "Berkeley_SC"

years <- c(2014, 2016, 2018, 2020, 2022)

files <- c("result", "edes", "precinct_distances", "residence_distances")
names(files) <- files
out_dir <- paste0(result_dir, "_appended_v2")

Berkeley_appended <- lapply(files, function(file){
  append_fields(
    config_name = config_name, 
    config_dir = config_dir, 
    result_dir = result_dir, 
    location = location, 
    file = file, 
    years = years
  )
})

if(!dir.exists(out_dir)) dir.create(out_dir)
lapply(files, function(file){
  lapply(years, function(year){
    write.csv(
      Berkeley_appended[[file]][[paste0(config_name, "_", year)]], 
      file = paste0(out_dir, "/", config_dir,".", config_name, "_", year, "_", file, ".csv"),
      row.names = FALSE
    )
  })
})