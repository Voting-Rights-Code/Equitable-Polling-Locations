library(data.table)

driving <- fread('datasets/driving/Gwinnett_County_GA/Gwinnett_County_GA_driving_distances.csv')

testing_base <- fread('datasets/polling/testing/testing_2020.csv') 
testing_base_dest_orig <- testing_base[ , c('id_orig', 'id_dest')] 

testing_driving <- merge(testing_base_dest_orig, driving, all.x = TRUE)

testing_driving_old <- fread('datasets/driving/testing/testing_driving_distances.csv')

all.equal(testing_driving, testing_driving_old)                        
#[1] "Different number of rows"

fwrite(testing_driving, 'datasets/driving/testing/testing_driving_distances.csv')

testing_driving_2020 <- merge(testing_base, testing_driving, all = TRUE, by = c('id_orig', 'id_dest'))
testing_driving_2020 <- testing_driving_2020[ , distance_m.x := NULL][, source := 'driving distance']
setnames(testing_driving_2020, 'distance_m.y', 'distance_m')

cols2 <- names(testing_driving_2020)[names(testing_driving_2020)!= 'V1']
setcolorder(testing_driving_2020, c('V1', cols2)) 

fwrite(testing_driving_2020, 'datasets/driving/testing/testing_driving_2020.csv')
