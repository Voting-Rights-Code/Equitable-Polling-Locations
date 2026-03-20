# Input Data

This document describes the input data sources used by the optimization model. If you are running the model against existing data already in the database, you may not need to create any of these files — see [to_run.md](to_run.md) for execution instructions.

When setting up a **new location** for the first time, the following inputs are needed:
1. A census API key (one-time setup)
1. A *manually generated* dataset of past and potential polling locations, consistent with local laws
1. A config file that contains the parameters for a given optimization
1. Optionally, a dataset of driving distances if driving distance analysis is desired

## Census Data (demographics and shapefiles)

The software requires a free census API key to run new counties. You can [apply on the census site](https://api.census.gov/data/key_signup.html) and be approved in seconds.

1. Create the directory `authentication_files/`
2. Inside `authentication_files/` create a file called `census_key.py`
3. The file should have a single line reading: `census_key = "YOUR_KEY_VALUE"`

The necessary data is automatically pulled from the census (if needed) when the model is run. However, one may also run `python -m python.utils.pull_census_data` to manually retrieve the data.

The software downloads and uses the following census datasets:

### Redistricting data (P3 and P4 tables)

Stored in `datasets/census/redistricting/<County_ST>/`

**P3 — Race for the Population 18 Years and Over** (`DECENNIALPL2020.P3-Data.csv`):

| Census Column | Maps to | Description |
|---------------|---------|-------------|
| P3_001N | population | Total voting-age (18+) population |
| P3_003N | white | White alone |
| P3_004N | black | Black or African American alone |
| P3_005N | native | American Indian and Alaska Native alone |
| P3_006N | asian | Asian alone |
| P3_007N | pacific_islander | Native Hawaiian and Other Pacific Islander alone |
| P3_008N | other | Some Other Race alone |
| P3_009N | multiple_races | Two or More Races |

Documentation: [Census API P3](https://api.census.gov/data/2020/dec/pl/groups/P3.html)

**P4 — Hispanic or Latino Origin** (`DECENNIALPL2020.P4-Data.csv`):

| Census Column | Maps to | Description |
|---------------|---------|-------------|
| P4_001N | population | Total voting-age (18+) population |
| P4_002N | hispanic | Hispanic or Latino |
| P4_003N | non_hispanic | Not Hispanic or Latino |

Documentation: [Census API P4](https://api.census.gov/data/2020/dec/pl/groups/P4.html)

### TIGER/Line Shapefiles

Stored in `datasets/census/tiger/<County_ST>/`

The model uses two shapefiles from the [TIGER/Line program](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html):

**Block shapefile** (`tl_<YYYY>_<FIPS>_tabblock<YY>.shp`):

| Column | Description |
|--------|-------------|
| GEOID20 | Census block identifier (format: `1000000US<FIPS><BLOCKNUM>`, e.g., `1000000US131510703153004`) |
| geometry | Polygon boundary of the census block |
| INTPTLAT20 | Latitude of the block centroid |
| INTPTLON20 | Longitude of the block centroid |

**Block group shapefile** (`tl_<YYYY>_<FIPS>_bg<YY>.shp`): Same structure as the block shapefile but at the block group level. Download instructions are identical to the block file.

Both files can be downloaded from the [TIGER/Line FTP Archive](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.2020.html#list-tab-790442341) by selecting the desired state and FIPS code.

## Potential Locations CSV

The model optimally assigns census blocks to polling locations chosen from this predefined list.

**File path:** `datasets/polling/<Location_ST>/<Location_ST>_potential_locations.csv`
**Example:** `datasets/polling/Gwinnett_County_GA/Gwinnett_County_GA_potential_locations.csv`

1. Manually create this file as a `.csv` with the columns defined below.
1. If running the model from the database, use `python run.py db_import_potential_locations_cli` to upload the data to the cloud.

### Columns

| Column Name | Type | Required | Description |
|-------------|------|----------|-------------|
| Location | STRING | Yes | Name of the actual or potential polling location (e.g., `Bethesda Senior Center`). |
| Address | STRING | Yes | Street address of the location. Format is flexible (e.g., `788 Hillcrest Rd NW, Lilburn, GA 20047`). |
| Location type | STRING | Yes | Classification of the site. See below for formatting rules. |
| Lat, Lon | STRING | Yes | Comma-separated latitude and longitude (e.g., `33.964717, -83.858272`). Can be obtained from Google Maps by right-clicking on the location. |

**Location type formatting:**
- **Existing polling locations** must include a year when the location was used. Examples: `EV_2022_2020`, `General_2020`, `Primary_2022_2020_2018`, `DropBox_2022`.
- **Potential locations** must include a category and the word `Potential` (case-sensitive). Examples: `Community Center - Potential`, `Library - Potential`, `Elec Day School - Potential`.

The `Location type` values are referenced by the `bad_types` and `penalized_sites` fields in config files.

## Configuration Files

The configuration files setting the parameters for model runs live in `datasets/configs/<config_set>/`. Each file is of the form `<config_name>.yaml`.

There may be multiple `<config_name>.yaml` files in the same `config_set` folder. However, each of these configs can only differ from each other by a single field (aside from `config_name`, `id`, and `created_at` fields). **If this property does not hold, the analysis files will not run.**

See `datasets/configs/template_configs/config_template_example.yaml_template` for a complete example.

### Creating config data

1. Create the desired `config_set` directory in `datasets/configs/`.
1. Copy `datasets/configs/template_configs/config_template_example.yaml_template` into the folder just created.
1. Change values as needed to create the desired configurations.
1. Two template-only fields control how the `.yaml` files will be generated:
    - `field_to_vary`: str — the name of the config field that varies across this set.
    - `new_range`: list — the list of desired values for that field. Can be a list of lists for array fields.
1. Run the generator:

```bash
python run.py auto_generate_config -b 'datasets/configs/<config_folder>/exemplar_config.yaml_template'
```

This will create a set of `.yaml` files in the indicated `config_folder`, each with a different name (a combination of the `field_to_vary` name and a value from `new_range`).

**Note:**
* This will also write these configs to the database. A database connection is required.
* If a file by the config name already exists in the config_folder, the script will not run.

**Example — varying precincts_open:**

In the `.yaml_template` file, define:
```yaml
field_to_vary: 'precincts_open'
new_range:
    - 15
    - 16
    - 17
    - 18
    - 19
    - 20
```
Then run:
```bash
python run.py auto_generate_config -b 'datasets/configs/DuPage_County_IL_potential_configs/example_config.yaml_template'
```

**Example — varying bad_types (list of lists):**

```yaml
field_to_vary: 'bad_types'
new_range:
    - - 'Elec Day School - Potential'
      - 'Elec Day Church - Potential'
      - 'bg_centroid'
    - - 'Elec Day Church - Potential'
      - 'bg_centroid'
    - - 'Elec Day School - Potential'
      - 'bg_centroid'
    - - 'bg_centroid'
```

### Config YAML Fields

The following fields are defined in the `PollingModelConfig` class (see `python/solver/model_config.py`). When configs are uploaded to the database, `id` and `created_at` fields are generated automatically. For database column-level details, see the `model_configs` table in the [data dictionary](data_dictionary.md).

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| config_set | str | Yes | — | The name of the set of configs this config belongs to. Should match the folder name. |
| config_name | str | Yes | — | Unique name of this config. Should match the file name (without `.yaml`). |
| location | str | Yes | — | Geographic location for the model. Must be of the form `<Location>_County_<ST>` or `Contained_in_<Location>_City_of_<ST>` to match census encoding. |
| census_year | str | Yes | `2020` | The census year that maps and demographic data are pulled from. |
| year | list[str] | Yes | — | Array of years of historical polling data relevant to this model (e.g., `['2020', '2022']`). Must not be empty. |
| bad_types | list[str] | No | `[]` | Location types to exclude from consideration. Values must match `Location type` entries in the `*_potential_locations.csv` file. |
| beta | float | Yes | — | Kolm-Pollak inequality aversion parameter. Range: `[-2, 0]`. `0` = indifference (uses mean distance). `-1` is a typical value. More negative values weight equity more heavily. |
| time_limit | int | Yes | — | Maximum solver runtime in seconds. |
| limits_gap | float | Yes | `0.02` | The acceptable optimality gap for the solver. Smaller values give more precise solutions but take longer. |
| penalized_sites | list[str] | No | `[]` | Location types where polling placement is penalized — used only if it improves access by a calculated threshold. Values must match `Location type` entries in the `*_potential_locations.csv` file. When used, generates three additional log files: `...model2.log`, `...model3.log`, and `...penalty.log`. See [arXiv:2401.15452](https://doi.org/10.48550/arXiv.2401.15452) for details. |
| precincts_open | int | No | `null` | Total number of precincts to open. If null, defaults to the number of existing polling places in the data. |
| maxpctnew | float | Yes | — | Maximum fraction of new (non-incumbent) locations permitted. Range: `[0, 1]`. `1` = all locations may be new. |
| minpctold | float | Yes | — | Minimum fraction of incumbent locations that must be retained. Range: `[0, 1]`. `0` = none required. |
| max_min_mult | float | Yes | — | Multiplicative factor for the max-min distance constraint. Should be `>= 1`. Smaller values reduce compute time. |
| capacity | float | Yes | — | Multiplicative factor for the capacity constraint. Should be `>= 1`. If not paired with `fixed_capacity_site_number`, capacity varies with the number of precincts. |
| fixed_capacity_site_number | int | No | `null` | If set, holds per-location capacity constant at this number of people, rather than varying with the number of open precincts. |
| driving | bool | No | `false` | If `true`, use driving distances (requires driving distance data to be available). If `false`, use haversine (straight-line) distances. |
| log_distance | bool | No | `false` | If `true`, the optimization uses the natural log of distances instead of raw distances. |


## OPTIONAL: Driving Distances CSV

Driving distance data is only required when the config parameter `driving` is set to `True`. These distances must be calculated externally (e.g., using Open Street Map routing data).

**File path:** `datasets/driving/<Location>/<Location>_driving_distances.csv`
**Example:** `datasets/driving/Gwinnett_County_GA/Gwinnett_County_GA_driving_distances.csv`

If running the model from the database, use `python run.py db_import_driving_distances_cli` to upload the data to the cloud. See [database](database.md) for details.

### Columns

| Column Name | Type | Required | Description |
|-------------|------|----------|-------------|
| id_orig | STRING | Yes | Census block group GEOID. Must match the `GEOID20` values (without the `1000000US` prefix) from the TIGER shapefile `datasets/census/tiger/<County_ST>/tl_<YYYY>_<FIPS>_tabblock<YY>.shp`. Example: `131510703153004`. |
| id_dest | STRING | Yes | Name of the polling/potential location. Must match a `Location` value from `datasets/polling/<County_ST>/<County_ST>_potential_locations.csv`. Example: `Bethesda Senior Center`. |
| distance_m | FLOAT | Yes | Driving distance in meters from `id_orig` to `id_dest`. Example: `10040.72`. |

**Note:** When imported to the database, a `source` column is automatically added with the value `driving distance`. This column does not need to be in the CSV file.

