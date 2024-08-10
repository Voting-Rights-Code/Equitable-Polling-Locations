library(here)
#######
#Change directory
#######
setwd(here())

#######
#source functions
#######
source('result analysis/graph_functions_2.R')

#######
#Set Constants
#######
#Location must be part of config folder string

LOCATION = 'DeKalb_GA'
CONFIG_FOLDER = 'DeKalb_GA_no_bg_school_configs'

config_list<- read_config(CONFIG_FOLDER)
foo <- process_configs_dt(CONFIG_FOLDER)

bar <- combine_results(LOCATION, CONFIG_FOLDER, 'edes')
baz <- read_result_data(LOCATION, CONFIG_FOLDER)