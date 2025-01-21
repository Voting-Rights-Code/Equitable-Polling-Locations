

# #get data to run regression

# regression_data <- get_regression_data(LOCATION, config_df_list[[4]])
# descriptor_list <- unique(regression_data$descriptor)
# reference <- descriptor_list[grepl(REFERENCE_TAG, descriptor_list)]
# regression_data <- calculate_pct_change(regression_data, reference)

# #run regeression by descriptor and store coefs in a data frame
# distance_model <- regression_data[, as.list(coef(lm(distance_m ~ pop_density_km  + pct_black + pop_density_km*pct_black),  weights = population )), by = descriptor]
# setnames(distance_model, c('(Intercept)', 'pop_density_km', 'pct_black','pop_density_km:pct_black'), c('intercept', 'density_coef', 'pct_black_coef', 'density_black_interaction_coef'))
# #fwrite(distance_model, paste0(COUNTY, '_distance_model.csv'))

# change_model<- regression_data[, as.list(coef(lm(pct_extra_in_2022 ~ pop_density_km  + pct_black + pop_density_km*pct_black),  weights = population )), by = descriptor]
# setnames(change_model, c('(Intercept)', 'pop_density_km', 'pct_black','pop_density_km:pct_black'), c('intercept', 'density_coef', 'pct_black_coef', 'density_black_interaction_coef'))
# #fwrite(change_model, paste0(COUNTY, '_pct_change_model.csv'))
