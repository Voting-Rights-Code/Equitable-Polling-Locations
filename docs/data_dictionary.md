# Data Dictionary

This document provides column-level definitions for all database tables and views in the `equitable_polling_locations_prod` BigQuery dataset. For an overview of the database, see [database](database.md).

Demographic population fields in this dataset are sourced from the U.S. Census Bureau's 2020 Decennial Census, specifically:
- **Race data:** Table P3 (Race for the Population 18 Years and Over)
- **Ethnicity data:** Table P4 (Hispanic or Latino Origin by Race for the Population 18 Years and Over)

All population counts represent the voting-age population (18+) at the census block group level.

---

## Tables

### model_configs

Stores the configuration parameters used to generate optimization model output. Each unique combination of parameters produces one record (deduplicated by SHA-1 hash).

| Column | Type | Mode | Description |
|--------|------|------|-------------|
| id | STRING(40) | REQUIRED | Primary key. SHA-1 hash of all non-date config columns, ensuring identical configs share the same ID. |
| config_set | STRING(256) | REQUIRED | The name of the set of configs this config belongs to (e.g., `Gwinnett_County_GA_driving_no_bg_no_ed_configs`). |
| config_name | STRING(256) | REQUIRED | The name of this specific config within the set (e.g., `Gwinnett_County_GA_driving_no_bg_no_ed_14`). |
| location | STRING(256) | NULLABLE | The geographic location for this model (e.g., `Gwinnett_County_GA`). |
| year | ARRAY\<STRING(256)\> | NULLABLE | An array of census years used in this model. |
| bad_types | ARRAY\<STRING(256)\> | NULLABLE | Location types excluded from consideration in this model (e.g., fire stations). |
| beta | FLOAT | NULLABLE | The Kolm-Pollak inequality aversion parameter. Range: [-2, 0]. 0 = indifference (uses mean distance); -1 is a typical value. More negative values weight equity more heavily. |
| time_limit | FLOAT | NULLABLE | Maximum solver runtime in seconds. |
| limits_gap | FLOAT | NULLABLE | The acceptable optimality gap for the solver (default: 0.02). |
| penalized_sites | ARRAY\<STRING(256)\> | NULLABLE | Locations where polling placement is penalized, used only if absolutely necessary for coverage (e.g., fire stations). |
| precincts_open | INTEGER | NULLABLE | Total number of precincts to open. If not specified, defaults to the number of polling places identified in the data. |
| maxpctnew | FLOAT | NULLABLE | Maximum fraction of new (non-incumbent) polling locations permitted. Default: 1.0 (all locations may be new). |
| minpctold | FLOAT | NULLABLE | Minimum fraction of incumbent polling locations that must be retained. Default: 0.0 (none required). |
| max_min_mult | FLOAT | NULLABLE | Multiplicative factor for the maximum-minimum distance constraint. Should be >= 1. Default: 1.0. |
| capacity | FLOAT | NULLABLE | Multiplicative factor for the capacity constraint. Should be >= 1. Default: 1.0. If not paired with `fixed_capacity_site_number`, capacity varies with the number of precincts. |
| driving | BOOLEAN | NULLABLE | If true, use driving distances (requires driving distance data). If false, use haversine (straight-line) distances. |
| fixed_capacity_site_number | INTEGER | NULLABLE | If set, holds the per-location capacity constant at this number of people, rather than varying with the number of open precincts. |
| log_distance | BOOLEAN | NULLABLE | If true, the optimization uses the natural log of distances instead of raw distances. |
| census_year | STRING(4) | NULLABLE | The census year for the distance source data. Default: `2020`. |
| created_at | DATETIME | REQUIRED | Timestamp when this config record was created (UTC). |

---

### model_runs

Records each execution of the optimization model against a config. A config may have multiple runs; only the most recent successful run is used in views.

| Column | Type | Mode | Description |
|--------|------|------|-------------|
| id | STRING(36) | REQUIRED | Primary key. UUID generated at creation. |
| model_config_id | STRING(40) | REQUIRED | Foreign key to `model_configs.id`. The config this run was executed against. |
| distance_data_set_id | STRING(36) | NULLABLE | Foreign key to `distance_data_sets.id`. The distance data used for this run. |
| username | STRING(256) | NULLABLE | Username of the person who executed this run. |
| commit_hash | STRING(256) | NULLABLE | Git commit hash of the codebase at the time of this run. |
| created_at | DATETIME | REQUIRED | Timestamp when this run was created (UTC). |
| success | BOOLEAN | REQUIRED | True if this run completed successfully. Only successful runs appear in views. Default: false. |

---

### potential_locations

A growing list of historic and candidate polling locations for each geographic area. These do not include distance calculations. Must be imported before any distance-related data.

| Column | Type | Mode | Description |
|--------|------|------|-------------|
| id | STRING(36) | REQUIRED | Primary key. UUID generated at creation. |
| potential_locations_set_id | STRING(36) | REQUIRED | Foreign key to `potential_locations_sets.id`. The import set this record belongs to. |
| location | STRING(256) | REQUIRED | Name of the polling site (e.g., `Gwinnett County Fairgrounds`). |
| address | STRING(256) | REQUIRED | Street address of the polling site. |
| location_type | STRING(256) | REQUIRED | Classification of the site (e.g., `Polling`, `Potential Church`, `Potential School`). Values prefixed with `Potential` indicate candidate locations not currently used. |
| lat_lon | STRING(256) | REQUIRED | Latitude and longitude as a comma-separated string (e.g., `33.9519,-84.0701`). Note: uses `lon`, not `long`. |

---

### potential_locations_sets

Metadata for each import batch of potential locations data.

| Column | Type | Mode | Description |
|--------|------|------|-------------|
| id | STRING(36) | REQUIRED | Primary key. UUID generated at creation. |
| location | STRING(256) | REQUIRED | The geographic location name (e.g., `Gwinnett_County_GA`). |
| created_at | DATETIME | REQUIRED | Timestamp when this set was imported (UTC). |

---

### driving_distances

Pairwise driving distances between census block group centroids and polling/potential locations. Optional — only needed when configs use `driving = true`.

| Column | Type | Mode | Description |
|--------|------|------|-------------|
| id | STRING(36) | REQUIRED | Primary key. UUID generated at creation. |
| driving_distance_set_id | STRING(36) | REQUIRED | Foreign key to `driving_distance_sets.id`. The import set this record belongs to. |
| id_orig | STRING(256) | REQUIRED | Origin identifier — the census block group GEOID. |
| id_dest | STRING(256) | REQUIRED | Destination identifier — the polling/potential location. |
| distance_m | FLOAT | REQUIRED | Driving distance in meters from origin to destination. |
| source | STRING(256) | REQUIRED | Source of the driving distance data (e.g., `driving distance`). |

---

### driving_distance_sets

Metadata for each import batch of driving distance data.

| Column | Type | Mode | Description |
|--------|------|------|-------------|
| id | STRING(36) | REQUIRED | Primary key. UUID generated at creation. |
| census_year | STRING(4) | REQUIRED | The census year the block group definitions reference (e.g., `2020`). |
| map_source_date | STRING(8) | REQUIRED | The date of the map source data used to compute driving distances (e.g., Open Street Map extract date). |
| location | STRING(256) | REQUIRED | The geographic location name (e.g., `Gwinnett_County_GA`). |
| created_at | DATETIME | REQUIRED | Timestamp when this set was imported (UTC). |

---

### distance_data

The intermediate distance dataset used directly by the optimizer. Each row represents one origin–destination pair with distance, demographic, and coordinate data. Built from potential locations and optionally driving distances.

| Column | Type | Mode | Description |
|--------|------|------|-------------|
| id | STRING(36) | REQUIRED | Primary key. UUID generated at creation. |
| distance_data_set_id | STRING(36) | REQUIRED | Foreign key to `distance_data_sets.id`. The import set this record belongs to. |
| id_orig | STRING(256) | REQUIRED | Origin identifier — the census block group GEOID. |
| id_dest | STRING(256) | REQUIRED | Destination identifier — the polling/potential location. |
| distance_m | FLOAT | NULLABLE | Distance in meters from origin to destination. May be haversine or driving distance, and may be log-transformed, depending on the parent `distance_data_sets` record's `driving` and `log_distance` flags. |
| address | STRING(256) | REQUIRED | Street address of the destination polling/potential location. |
| dest_lat | FLOAT | REQUIRED | Latitude of the destination. |
| dest_lon | FLOAT | REQUIRED | Longitude of the destination. |
| orig_lat | FLOAT | REQUIRED | Latitude of the origin (census block group centroid). |
| orig_lon | FLOAT | REQUIRED | Longitude of the origin (census block group centroid). |
| location_type | STRING(256) | REQUIRED | Classification of the destination site (e.g., `Polling`, `Potential Church`). |
| dest_type | STRING(256) | REQUIRED | Whether the destination is an existing `polling` location or a `potential` candidate. |
| population | INTEGER | REQUIRED | Total voting-age population (18+) of the origin census block group. Census table P3_001N. |
| hispanic | INTEGER | REQUIRED | Hispanic or Latino voting-age population. Census table P4_002N. |
| non_hispanic | INTEGER | REQUIRED | Not Hispanic or Latino voting-age population. Census table P4_003N. |
| white | INTEGER | REQUIRED | White alone voting-age population. Census table P3_003N. |
| black | INTEGER | REQUIRED | Black or African American alone voting-age population. Census table P3_004N. |
| native | INTEGER | REQUIRED | American Indian or Alaska Native alone voting-age population. Census table P3_005N. |
| asian | INTEGER | REQUIRED | Asian alone voting-age population. Census table P3_006N. |
| pacific_islander | INTEGER | REQUIRED | Native Hawaiian and Other Pacific Islander alone voting-age population. Census table P3_007N. |
| other | INTEGER | REQUIRED | Some other race alone voting-age population. Census table P3_008N. |
| multiple_races | INTEGER | REQUIRED | Two or more races voting-age population. Census table P3_009N. |
| source | STRING(256) | REQUIRED | Distance calculation method (e.g., `haversine distance`, `driving distance`, `log haversine distance`, `log driving distance`). |

---

### distance_data_sets

Metadata for each import batch of distance data. Links back to the potential locations and optionally driving distances used to build it.

| Column | Type | Mode | Description |
|--------|------|------|-------------|
| id | STRING(36) | REQUIRED | Primary key. UUID generated at creation. |
| location | STRING(256) | REQUIRED | The geographic location name (e.g., `Gwinnett_County_GA`). |
| census_year | STRING(4) | REQUIRED | The census year the block group definitions reference (e.g., `2020`). |
| created_at | DATETIME | REQUIRED | Timestamp when this set was imported (UTC). |
| log_distance | BOOLEAN | REQUIRED | True if the distances in the associated `distance_data` rows are log-transformed. |
| driving | BOOLEAN | REQUIRED | True if the distances use driving distances; false if haversine. |
| potential_locations_set_id | STRING(36) | REQUIRED | Foreign key to `potential_locations_sets.id`. The potential locations data this distance data was built from. |
| driving_distance_set_id | STRING(36) | NULLABLE | Foreign key to `driving_distance_sets.id`. The driving distance data used, if applicable. Null when `driving` is false. |

---

### results

The matched origin–destination pairs from the optimization model output. Each row is a residence block group matched to its assigned polling location for a given model run.

| Column | Type | Mode | Description |
|--------|------|------|-------------|
| id | STRING(36) | REQUIRED | Primary key. UUID generated at creation. |
| model_run_id | STRING(36) | REQUIRED | Foreign key to `model_runs.id`. The model run that produced this result. |
| id_orig | STRING(256) | NULLABLE | Origin census block group GEOID. |
| id_dest | STRING(256) | NULLABLE | Destination polling location identifier. |
| distance_m | FLOAT | NULLABLE | Distance in meters from origin to assigned destination. If `log_distance` was true in the config, this is the exponentiated (original-scale) distance. |
| haversine_m | FLOAT | NULLABLE | Haversine (straight-line) distance in meters, when available. |
| county | STRING(256) | NULLABLE | County name. |
| address | STRING(256) | NULLABLE | Street address of the assigned polling location. |
| dest_lat | FLOAT | NULLABLE | Latitude of the destination. |
| dest_lon | FLOAT | NULLABLE | Longitude of the destination. |
| orig_lat | FLOAT | NULLABLE | Latitude of the origin (census block group centroid). |
| orig_lon | FLOAT | NULLABLE | Longitude of the origin (census block group centroid). |
| location_type | STRING(256) | NULLABLE | Classification of the destination site. |
| dest_type | STRING(256) | NULLABLE | Whether the destination is `polling` or `potential`. |
| population | INTEGER | NULLABLE | Total voting-age population of the origin block group. |
| hispanic | INTEGER | NULLABLE | Hispanic or Latino voting-age population. |
| non_hispanic | INTEGER | NULLABLE | Not Hispanic or Latino voting-age population. |
| white | INTEGER | NULLABLE | White alone voting-age population. |
| black | INTEGER | NULLABLE | Black or African American alone voting-age population. |
| native | INTEGER | NULLABLE | American Indian or Alaska Native alone voting-age population. |
| asian | INTEGER | NULLABLE | Asian alone voting-age population. |
| pacific_islander | INTEGER | NULLABLE | Native Hawaiian and Other Pacific Islander alone voting-age population. |
| other | INTEGER | NULLABLE | Some other race alone voting-age population. |
| multiple_races | INTEGER | NULLABLE | Two or more races voting-age population. |
| weighted_dist | FLOAT | NULLABLE | Population-weighted distance: `population * distance_m`. |
| kp_factor | FLOAT | NULLABLE | Kolm-Pollak exponential factor: `e^(-beta * alpha * distance_m)`. Used in EDE calculation. |
| new_location | INTEGER | NULLABLE | 1 if the assigned location is new (not a current polling place); 0 otherwise. |
| matching | INTEGER | NULLABLE | 1 if this origin is matched to this destination in the optimal solution; 0 otherwise. In the results table, all rows have `matching = 1`. |
| source | STRING(256) | NULLABLE | Distance calculation method (e.g., `haversine distance`, `driving distance`). |

---

### edes

The Equally Distributed Equivalent (EDE) distance summary by demographic group for each model run. The EDE is the Kolm-Pollak equity-adjusted average distance — a single number per demographic that accounts for both mean distance and inequality.

| Column | Type | Mode | Description |
|--------|------|------|-------------|
| id | STRING(36) | REQUIRED | Primary key. UUID generated at creation. |
| model_run_id | STRING(36) | REQUIRED | Foreign key to `model_runs.id`. The model run that produced this EDE output. |
| demographic | STRING(256) | NULLABLE | Demographic group name (e.g., `population`, `white`, `black`, `hispanic`, `asian`, `native`). |
| weighted_dist | FLOAT | NULLABLE | Sum of population-weighted distances for this demographic group. |
| avg_dist | FLOAT | NULLABLE | Simple average distance for this demographic group (weighted_dist / demo_pop). |
| demo_res_obj_summand | FLOAT | NULLABLE | Sum of `demo_pop * e^(-beta * alpha * distance)` across all residences for this demographic. Intermediate value in EDE calculation. |
| demo_pop | INTEGER | NULLABLE | Total population count for this demographic group. |
| avg_kp_weight | FLOAT | NULLABLE | Average KP weight: `demo_res_obj_summand / demo_pop`. |
| y_ede | FLOAT | NULLABLE | The EDE value: `(-1 / (beta * alpha)) * ln(avg_kp_weight)`. The equity-adjusted equivalent distance. Lower values indicate more equitable outcomes. |
| source | STRING(256) | NULLABLE | Distance calculation method used. |

---

### precinct_distances

Average distance traveled by each demographic group to each assigned polling location (precinct). Aggregated by destination.

| Column | Type | Mode | Description |
|--------|------|------|-------------|
| id | STRING(36) | REQUIRED | Primary key. UUID generated at creation. |
| model_run_id | STRING(36) | REQUIRED | Foreign key to `model_runs.id`. The model run that produced this output. |
| id_dest | STRING(256) | NULLABLE | Destination (precinct/polling location) identifier. |
| demographic | STRING(256) | NULLABLE | Demographic group name. |
| weighted_dist | FLOAT | NULLABLE | Sum of population-weighted distances for this demographic assigned to this precinct. |
| demo_pop | INTEGER | NULLABLE | Total population of this demographic assigned to this precinct. |
| avg_dist | FLOAT | NULLABLE | Average distance for this demographic to this precinct (weighted_dist / demo_pop). |
| source | STRING(256) | NULLABLE | Distance calculation method used. |

---

### residence_distances

Average distance traveled by each demographic group from each residence (census block group). Aggregated by origin.

| Column | Type | Mode | Description |
|--------|------|------|-------------|
| id | STRING(36) | REQUIRED | Primary key. UUID generated at creation. |
| model_run_id | STRING(36) | REQUIRED | Foreign key to `model_runs.id`. The model run that produced this output. |
| id_orig | STRING(256) | NULLABLE | Origin (census block group) GEOID. |
| demographic | STRING(256) | NULLABLE | Demographic group name. |
| weighted_dist | FLOAT | NULLABLE | Sum of population-weighted distances for this demographic from this residence. |
| demo_pop | INTEGER | NULLABLE | Total population of this demographic in this block group. |
| avg_dist | FLOAT | NULLABLE | Average distance for this demographic from this residence (weighted_dist / demo_pop). |
| source | STRING(256) | NULLABLE | Distance calculation method used. |

---

### alembic_version

Internal table used by the Alembic migration tool to track schema version.

| Column | Type | Mode | Description |
|--------|------|------|-------------|
| version_num | STRING(32) | REQUIRED | The revision ID of the most recently applied migration. |

---

## Views

### model_config_runs

Associates each config with its most recent successful model run. Filters out outdated data and incomplete runs. Uses the latest config record per `(config_set, config_name)` pair and the most recent successful `model_runs` entry for that config.

**Columns:** All columns from `model_configs`, plus:

| Column | Type | Description |
|--------|------|-------------|
| model_run_id | STRING(36) | The `model_runs.id` of the most recent successful run. |
| run_at | DATETIME | The `model_runs.created_at` timestamp of that run. |

---

### edes_extras

Joins `edes` with `model_config_runs` to associate the most recent EDE data with its generating config.

**Columns:** All columns from `edes`, plus:

| Column | Type | Description |
|--------|------|-------------|
| location | STRING(256) | From `model_config_runs`. |
| year | ARRAY\<STRING\> | From `model_config_runs`. |
| precincts_open | INTEGER | From `model_config_runs`. |
| config_id | STRING(40) | The `model_configs.id`. |
| config_set | STRING(256) | From `model_config_runs`. |
| config_name | STRING(256) | From `model_config_runs`. |

---

### precinct_distances_extras

Joins `precinct_distances` with `model_config_runs` to associate the most recent precinct distance data with its generating config.

**Columns:** All columns from `precinct_distances`, plus the same additional columns as `edes_extras` (location, year, precincts_open, config_id, config_set, config_name).

---

### residence_distances_extras

Joins `residence_distances` with `model_config_runs` to associate the most recent residence distance data with its generating config.

**Columns:** All columns from `residence_distances`, plus the same additional columns as `edes_extras` (location, year, precincts_open, config_id, config_set, config_name).

---

### results_extras

Joins `results` with `model_config_runs` to associate the most recent results data with its generating config.

**Columns:** All columns from `results`, plus the same additional columns as `edes_extras` (location, year, precincts_open, config_id, config_set, config_name).

---

### latest_driving_distance_sets

Returns the most recently imported `driving_distance_sets` entry for each location. Uses `ROW_NUMBER()` partitioned by `location`, ordered by `created_at DESC`, selecting only row 1.

**Columns:** All columns from `driving_distance_sets` (id, census_year, map_source_date, location, created_at).
