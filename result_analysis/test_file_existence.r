library(here)
library(mgsub)

setwd(here())

check_config_exists <- function(result_folder){
    all_files <- list.files(result_folder)
    endings <- c('_edes.csv', '_precinct_distances.csv', '_residence_distances.csv', '_result.csv')
    drop_endings <- mgsub(all_files, endings, c('','','',''))
    configs <- unique(drop_endings)
    config_paths <- paste0(gsub('\\.', '/', configs), '.yaml')
    config_exists <- sapply(config_paths, file.exists)
    if (all(config_exists)){
        return_str <- paste('all configs exist')
    } else{
        bad_configs <- config_paths[!config_exists]
        return_str <- paste('problem with config: ', bad_configs)
    }
    return(return_str)
}

all_dirs <- list.dirs(recursive = F)
result_dirs <- all_dirs[grepl('results', all_dirs)]

foo <- sapply(result_dirs, function(result)check_config_exists(result))

#foo <- check_config_exists(result_dirs[7])