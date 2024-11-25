library(here)

#######
#Change directory
#######
setwd(here())

#######
#source functions
#######

source('result analysis/graph_functions.R')

#######
#Set Constants
#######

#NOTE: not all config sets are currently loaded.
CONFIG_SET = "Cobb_GA_no_bg_school_configs"

#This seems to return empty dataframes
foo <- query_result_data(config_set = CONFIG_SET)

bar <- query_result_data(config_set = ORIG_CONFIG_FOLDER)

#try just pulling the result data down
query <- "SELECT * FROM polling.result"

con <- dbConnect(
    bigrquery::bigquery(),
    project = project,
    dataset = dataset
  )

data <- dbGetQuery(con, query)
#> dim(data)
#[1] 873677     26

config_set_list <- unique(data$config_set)

bar <- query_result_data(config_set = config_set_list[1])
#> lapply(bar, dim)
#[[1]]
#[1] 0 9

#[[2]]
#[1]  0 26

#[[3]]
#[1] 0 7

#[[4]]
#[1] 0 7