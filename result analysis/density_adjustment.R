# Load Libraries, Data, and Source
library(tidyverse)
library(here)
library(sf)

source(here('result analysis', 'graph_functions.R'))
source(here('result analysis', 'map_functions.R'))

LOCATION = "Loudon_County_VA"
CONFIG_FOLDER <- 'Engage_VA_2024_configs'
config_df_list <- read_result_data(LOCATION, CONFIG_FOLDER, 'placement')

raw_df <- get_regression_data(LOCATION, config_df_list[[4]])

# get final dataset
df <- raw_df %>%
  as_tibble() %>%
  select(id_orig,
         distance = distance_m,
         num_white = white,
         num_black = black,
         num_native = native,
         num_asian = asian,
         num_pacific_islander = pacific_islander,
         num_other = other,
         num_multiple_races = multiple_races,
         pct_white,
         population,
         density = pop_density_km,
         geometry) %>%
  mutate(race_bin = cut(pct_white, breaks = c(-1, 25, 50, 75, 101), 
                        labels = c("0-25% White", "25-50% White", "50-75% White", "75-100% White")))


# Calculate Density-Adjusted Distance -------------------------------------
# Run Regression for Density Adjustment
# density-squared or other transformations could be added here
fit1 <- df %>% 
  filter(density < quantile(df$density, .98),
         density > quantile(df$density, .02)) %>%
  lm(distance ~ density, weights = population, data = .)

# Extract the slope
density_slope <- coef(fit1)[2]

# Get mean value of density
mean_density <- mean(df$density)

# Add the density-adjusted distance to DF
df <- df %>%
  mutate(
    density_adjusted_distance = distance - (density_slope * (density - mean_density))
  )

# Make Data Frames for Plotting -------------------------------------------
# Pivot the data to a longer format and summarize by race
df_summary <- df %>%
  pivot_longer(cols = starts_with("num_"), names_to = "race", values_to = "count") %>%
  mutate(race = sub("num_", "", race)) %>%
  group_by(race) %>%
  summarise(
    n = sum(count),
    avg_density_adjusted_distance = weighted.mean(density_adjusted_distance, count, na.rm = TRUE),
    avg_distance = weighted.mean(distance, count, na.rm = TRUE)
  )

# Binned % white
df_summary_perc <- df %>%
  group_by(race_bin) %>%
  summarise(
    avg_density_adjusted_distance = weighted.mean(density_adjusted_distance, population, na.rm = TRUE),
    avg_distance = weighted.mean(distance, population, na.rm = TRUE)
  )  %>%
  pivot_longer(cols = c(avg_density_adjusted_distance, avg_distance), names_to = "type", values_to = "value") %>%
  mutate(type = recode(type,
                       avg_density_adjusted_distance = "Density Adjusted Distance",
                       avg_distance = "Unadjusted Distance"))

# Make Plots --------------------------------------------------------------
# This shows how adjusted distance compares to distance
df %>%
  ggplot(aes(x= distance, y = density_adjusted_distance, color = density)) +
  geom_point()

# Compare average adj. and unadj. distances by race
df_summary %>%
  pivot_longer(cols = c(avg_density_adjusted_distance, avg_distance), names_to = "type", values_to = "value") %>%
  mutate(type = recode(type,
                       avg_density_adjusted_distance = "Adjusted",
                       avg_distance = "Unadjusted")) %>%
  ggplot(aes(x = race, y = value, fill = type)) +
  geom_bar(stat = "identity", position = "dodge") +
  labs(x = "", y = "Average Distance (m)", fill = "Type", 
       title = "Avgerage Distances by Race") +
  scale_fill_manual("legend", values = c("Unadjusted" = "grey", "Adjusted" = "#0b80a1")) +
  theme_minimal() +
  coord_flip() +
  guides(fill = guide_legend(reverse = TRUE)) +
  theme(legend.title=element_blank())

# same as above but using % white bins
ggplot(df_long_summary, aes(x = race_bin, y = value, fill = type)) +
  geom_bar(stat = "identity", position = "dodge") +
  labs(y = "Average Distance (m)", fill = "Type", 
       title = "Average Distances by % White") +
  theme_minimal() +
  theme(axis.text.x = element_text(angle = 45, hjust = 1)) +
  coord_flip() +
  guides(fill = guide_legend(reverse = TRUE))

# These scatterplots are a little hard to read but shows relationship between race, distance, and density
df %>%
  mutate(majority_white = ifelse(pct_white > 50, "Majority White", "Majority Non-White")) %>% 
  select(majority_white, 
         density, 
         "unadjusted" = distance, 
         "adjusted" = density_adjusted_distance, 
         population) %>%
  pivot_longer(cols = c(unadjusted, adjusted), names_to = "distance_type", values_to = "distance") %>%
  ggplot(aes(x = log(density), y = distance, alpha = population)) +
    geom_point() +
    facet_grid(distance_type ~ majority_white) +
    labs(x = "log(Density)", y = "Distance") +
    theme_minimal()

#pct_white by distance (adjusted and unadjusted)
df %>%
  select(pct_white, 
         "unadjusted" = distance, 
         "adjusted" = density_adjusted_distance,
         population) %>%
  pivot_longer(cols = c(unadjusted, adjusted), values_to = "distance", names_to = "distance_type") %>%
  ggplot(aes(x=pct_white, y = distance, alpha = population)) +
  geom_point() +
  facet_wrap(~distance_type)
  ylim(0, 25000) +
  theme_minimal()

# Make Maps ---------------------------------------------------------------
# These show areas that are denser and more/less white
df %>% 
  select(geometry, density) %>%
  mutate(density_quantile = ntile(density, 10)) %>%
  st_as_sf() %>%
  st_simplify(dTolerance = 30) %>%
  ggplot(aes(fill = density_quantile, color = density_quantile)) +
  geom_sf() +
  labs(title="density") +
  theme_void()

df %>% 
  select(geometry, pct_white) %>%
  mutate(pct_nonwhite = 100-pct_white) %>%
  mutate(nonwhite_quantile = ntile(pct_nonwhite, 6)) %>%
  st_as_sf() %>%
  st_simplify(dTolerance = 30) %>%
  ggplot(aes(fill = nonwhite_quantile, color = nonwhite_quantile)) +
  geom_sf() +
  labs(title="non-white") +
  theme_void()

df %>% 
  select(geometry, distance) %>%
  st_as_sf() %>%
  st_simplify(dTolerance = 30) %>%
  ggplot(aes(fill = distance, color = distance)) +
  geom_sf() +
  theme_void()


# A different approach ----------------------------------------------------
# controlling for density attenuates but does not eliminate the effect of race
df %>% 
  filter(density < quantile(df$density, .98),
         density > quantile(df$density, .02)) %>%
  lm(distance ~ pct_white, weights = population, data = .) %>%
  summary()

df %>% 
  filter(density < quantile(df$density, .98),
         density > quantile(df$density, .02)) %>%
  lm(distance ~ density + pct_white, weights = population, data = .) %>%
  summary()


