library (data.table)

setwd('datasets/polling/South Carolina Temp')

#Pull in data
dt_22 <- fread('Polls_2022.csv')
dt_20 <- fread('Polls_2020.csv')
dt_18 <- fread('Polls_2018.csv')
dt_16 <- fread('Polls_2016.csv')
dt_14 <- fread('Polls_2014.csv')
sample <- fread('../DeKalb_GA/DeKalb_GA_locations_only.csv')

#add year
dt_14[ , Year := '2014']
dt_16[ , Year := '2016']
dt_18[ , Year := '2018']
dt_20[ , Year := '2020']
dt_22[ , Year := '2022']

#22 was from a different source than the rest. Change columns
dt_22[ , address := paste0(`Street Address`, ', ', City, ' ',`Zip Code`)]

#select columns for optimizer (22 handled differently)
to_keep22 <- c("Polling Site Name", "address", "Year", "County")
dt_22_short <- dt_22[ , ..to_keep22]
setnames(dt_22_short, c("Polling Site Name", 'County'), c("name", 'county_name'))


to_keep_pre22 <- c('name', 'address', 'Year', 'county_name')

dt_20_short <- dt_20[ , ..to_keep_pre22]
dt_18_short <- dt_18[ , ..to_keep_pre22]
dt_16_short <- dt_16[ , ..to_keep_pre22]
dt_14_short <- dt_14[ , ..to_keep_pre22]

#combine
all_dt <- list(dt_14_short, dt_16_short, dt_18_short, dt_20_short, dt_22_short)
big_dt <- rbindlist(all_dt)

#######
#start Cleaning
#######
county_count <- big_dt[ , .(num_polls = .N), by = county_name]
big_dt[county_name == 'Berkeley', county_name := 'BERKELEY'
     ][county_name == 'York', county_name := 'YORK'
     ][county_name == 'Greenville', county_name := 'GREENVILLE'        
     ]
#visual check confirms that duplicates arise in the original data due to being assigned for multiple precints
#since we are not recording precinct data, we drop these     
big_dt<- unique(big_dt)

#check duplicate names
name_groups <- big_dt[ , .(name_dups = .N), by = c('name', 'Year', 'county_name')]
dup_names <- name_groups[name_dups > 1, ]$name
big_dup_names <- big_dt[name %in% dup_names, ]

#check duplicate addresses 
address_groups <- big_dt[ , .(address_dups = length(unique(address))), by = c('name', 'county_name')]
multi_address <- address_groups[address_dups > 1, ]$name

big_dup_address <- big_dt[name %in% multi_address, ]


#There are 508 of these ma
bad_locations <- unique(big_dup_address$name)

#maybe time to do this by hand on a spreadsheet now.
fwrite(big_dt, "CLC_relevant_data.csv")

#####
#After hand cleaning
#####

cleaner <- fread("CLC_relevant_data.csv")

#Does every address have an unique name?
address_name <- cleaner[ , .(num_names = length(unique(name))), by = address]
address_name[num_names >1, ] #yes

#Does every name, count have an unique address?
name_county_address <- cleaner[ , .(num_address = length(unique(address))), by = c('name', 'county_name')]
name_county_address[num_address >1, ] #yes

#Is every address year pair unique
address_year_unique <- cleaner[ , .(address_year_count = .N), by = c('address', 'Year')]
address_year_unique[address_year_count >1,]#yes

#Is every name, county year pair unique
name_year_unique <- cleaner[ , .(name_year_count = .N), by = c('name', 'Year', 'county_name')]
name_year_unique[name_year_count >1,]#yes

########
#Label locations with years
########

dt <- cleaner[ , .(`Location type` = paste(Year, collapse = '_')), by = c('name', 'address', 'county_name')][ , `Location type` := paste('polling', `Location type`, sep = '_')]

setnames(dt, c('name', 'address'), c('Location', 'Address'))

########
#write to file by county
########
berkeley_dt <- dt[county_name == "BERKELEY", ][, county_name := NULL] 
greenville_dt <- dt[county_name == "GREENVILLE", ][, county_name := NULL]
lexington_dt <- dt[county_name == "LEXINGTON", ][,county_name := NULL]
richland_dt <- dt[county_name == 'RICHLAND', ][,county_name := NULL]
york_dt <- dt[county_name == 'YORK',][,county_name := NULL]

fwrite(berkeley_dt, '../Berkeley_SC/Berkeley_SC_locations_only.csv')
fwrite(greenville_dt, '../Greenville_County_SC/Greenville_County_SC_locations_only.csv')
fwrite(lexington_dt, '../Lexington_County_SC/Lexington_County_SC_locations_only.csv')
fwrite(richland_dt, '../Richland_County_SC/Richland_County_SC_locations_only.csv')
fwrite(york_dt, '../York_County_SC/York_County_SC_locations_only.csv')
########
#old stuff below
########
#fix these manually
good_address_1 <- big_dup_names[name == bad_locations[1], ]$address
big_dt <- big_dt[name == bad_locations[1], address := good_address_1[1]]
unique(big_dt[name == bad_locations[1], ]$address)

good_address_2 <- big_dup_names[name == bad_locations[2], ]$address
big_dt <- big_dt[name == bad_locations[2], address := good_address_2[2]]
unique(big_dt[name == bad_locations[2], ]$address)

#YIKES! there are two Faith Baptist Churches with different addresses in Greenville
#The ID is not the unique! this will cause lat / long and merge errors
good_address_3 <- big_dup_names[name == bad_locations[3], ]$address
big_dt <- big_dt[name == bad_locations[3] & grepl("Taylors", address), c('name','address') := list(paste(bad_locations[3], 'Taylors', sep = ' '), good_address_3[1])]
unique(big_dt[grepl(bad_locations[3], name), ]$address)
big_dt <- big_dt[name == bad_locations[3] & grepl("Simpsonville", address), c('name','address') := list(paste(bad_locations[3], 'Simpsonville', sep = ' '), good_address_3[2])]
unique(big_dt[grepl(bad_locations[3], name), ]$address)

#YIKES! there are two Philadelphia United Methodist Churches with different addresses in York
#The ID is not the unique! this will cause lat / long and merge errors
good_address_4 <- big_dup_names[name == bad_locations[4], ]$address
big_dt <- big_dt[name == bad_locations[4] & grepl("York", address), c('name','address') := list(paste(bad_locations[4], 'York', sep = ' '), good_address_4[1])]
unique(big_dt[grepl(bad_locations[4], name), ]$address)
big_dt <- big_dt[name == bad_locations[4] & grepl("Fort Mill", address), c('name','address') := list(paste(bad_locations[4], 'Fort Mill', sep = ' '), good_address_4[2])]
unique(big_dt[grepl(bad_locations[4], name), ]$address)

#drop dups after cleaning
big_dt<- unique(big_dt)

#check the result is clean
name_groups2 <- big_dt[ , .(name_dups = .N), by = c('name', 'Year', 'county_name')]
dim(name_groups2[name_dups > 1, ])

########
#Make location_type column
########
dt <- big_dt[ , .(years_str = paste(unique(Year), collapse = '_'), num_year = length(unique(Year))), by = c('name', 'address', 'county_name') 
            ][ , location_type := paste('polling', years_str, sep = '_')]
