library(data.table)
library(here)

setwd(here())



Dekalb_files <- list.files('DeKalb_County_GA_results')
Dekalb_result_files <- Dekalb_files[grepl('result', Dekalb_files)]

insert_V1 <- function(file_name){
    file_path <- paste0('DeKalb_County_GA_results/', file_name)
    dt <- fread(file_path)

    if (!("V1" %in% names(dt))){
        setnames(dt, '', 'V1')
        fwrite(dt, file_path)

    }
    return
}
sapply(Dekalb_result_files, function(x)insert_V1(x))