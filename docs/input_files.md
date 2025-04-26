# Input data
There are three sets of data needed to run the optimization and analysis in this program:
1. Census data for the county, aggregated at the block and block group level;
1. a *manually generated* dataset of past and potential polling locations, consistent with local laws;
1.   a config file that contains the parameters for a given optimization.

Additionally,
1. if one wishes to analyze driving distances, there is an additional input file to capture this data.

## Config data

In the database, config data is stored with a unique `config_set` and `config_name` pair. When stored locally, `config_set` corresponds to the config_folder, while `config_name` corresponds to the file (.yaml) in the config_folder.

There may be multiple `config_name`s sharing the same `config_set`. However, each of these datasets can only differ from each other by a single field (aside from `config_name`, `id` and `created_at` fields). **If this property does not hold, the analysis files will not run.**

### Creating config data
To create config data, create an examplar config file and put it in the desired folder. The exemplar config file
* must contain two extra fields that are not in the config file itself:
    * field to vary: str; the name of the field in the config file that is allowed to vary in this config set
    * new_range: list; the list of desired values that this field should take. Note, this can be a list of lists
* should not end in `.yaml`. In these example, the exemplar files ends in `.yaml_template`

Then run

 `python -m python.scripts.auto_generate_config -b 'config_folder/exemplar_config.yaml_template'

This will create a set of .yaml files in the indicaded `config_folder`, each with a different name (that is a combination of the indicated `field_to_change` and a value from the provided list.) It will also write these configs to the database.

**Note:**
* If a file by the config name already exists in the config_folder, the script will not run
* The fields of the exemplar_config MUST match the fields in the sql_alchemy model. Otherwise, this script will not run.

**Example:**
To generate a set of configs for DuPage County, IL where the number of precincts open varies from 15 to 20, define
`field_to_change: 'precints_open'`
`new_range:
    - 15
    - 16
    - 17
    - 18
    - 19
    - 20`
in the `.yaml_template` file and then run
```
python -m python.scripts.auto_generate_config -f 'DuPage_County_IL_potential_configs/example_config.yaml_template'
```
To generate a set of configs for DuPage County, IL where the set of bad locations varies are ['Elec Day School - Potential', 'Elec Day Church - Potential', 'bg_centroid'],  ['Elec Day Church - Potential', 'bg_centroid'], ['Elec Day School - Potential',  'bg_centroid'], and [ 'bg_centroid'] define
`field_to_change: 'bad_locations'`
`new_range:
    - - 'Elec Day School - Potential'
      - 'Elec Day Church - Potential'
      - 'bg_centroid'
    - - 'Elec Day Church - Potential'
      - 'bg_centroid'
    - - 'Elec Day School - Potential'
      - 'bg_centroid'
    - - 'bg_centroid'`
in the `.yaml_template` file and then run
```
python -m python.scripts.auto_generate_config -f 'DuPage_County_IL_potential_configs/example_config.yaml_template'
```
### Config fields
These fields are determined by the sql_alchemy config model. See `models/model_config.py`. In addition to the fields listed below, and `id`, and `created_at` field are generated when uploaded to the database.

* config_set
    * str
    * The name of the set of configs that this config belongs to.
* config_name
    * str
    * The name of this model config. '''
* location
    * str, nullable
    * Location for this model. Usually a county.
* year
    * List[str], nullable
    * An array of years of historical data relevant to this model
* bad_types
    * List[str], nullable
    * A list of location types not to be considered in this model
* beta
    * float, nullable
    * level of inequality aversion: [-2,0], where 0 indicates indifference, and thus uses the mean. -1 is a good number.
* time_limit
    * float, nullable
    * How long the solver should try to find a solution
*  penalized_sites
    * List[str], nullable
    * A list of locations for which the preference is to only place a polling location there if absolutely necessary for coverage.  A site in this list should be selected only if it improves access by x meters, where x is calculated according to the problem data. (See https://doi.org/10.48550/arXiv.2401.15452 for more information.) This option generates three additional log files: two for additional calls to the optimization solver ("...model2.log", "...model3.log") third ("...penalty.log") providing statistics related to the penalty heuristic.
* precincts_open
    * int, nullable
    * The total number of precincts to be used this year.
    * If no user input is given, this is calculated to be the number of
    polling places identified in the data.
* maxpctnew
    * float, nullable
    * The percent on new polling places (not already defined as a
    polling location) permitted in the data.
    * Default = 1. I.e. can replace all existing locations
* minpctold
    * float, nullable
    * The minimun number of polling places (those already defined as a
    polling location) permitted in the data.
    * Default = 0. I.e. can replace all existing locations
* max_min_mult
    * float, nullable
    * A multiplicative factor for the min_max distance caluclated
    from the data. Should be >= 1.
    * Default = 1.
* capacity
    * float, nullable
    * A multiplicative factor for calculating the capacity constraint. Should be >= 1.
    * Default = 1.
    * Note, if this is not paired with fixed_capacity_site_number, then the capacity changes as a function of number of precincts.
* fixed_capacity_site_number
    * int, nullable
    * The default number of open precincts if one wants to hold the number of people that can go to a location constant (as opposed to a function of the number of locations).
* driving
    * bool, nullable
    * Driving distances used if True and distance file exists in correct location
* log_distance
    * bool, nullable
    * Flag indicating whether or not the log of the distances is to be used in the optimization

## **Census Data (demographics and shapefiles)**:
The sofware requires a free census API key to run new counties. You can [apply on the cenus site](https://api.census.gov/data/key_signup.html) and be approved in seconds.

    1. Create the directory authentication_files/
    2. Inside authentication_files/ create a file called census_key.py
    3. The file should have a single line reading: census_key = "YOUR_KEY_VALUE"

If you are only running counties already in the repo you skip this step. However, it is needed to run counties for which data does not exist locally.

The script `pull_census_data.py`, which can also be run from the command line, pulls the following files from the 2020 US Census:
1. P3 (race) and P4 (ethnicity) files for the indicated county, at both the block and the block group level
    1. This is saved locally in the folder `datasets/census/redistricting`
2. Tiger shape files for the county at both the block and block group level.
    1. This is saved locally in the folder `datasets/census/tiger`

Eventually, this data will be loaded to the database as well. Until then, it is either stored locally, or needs to be downloaded for each call to `model_run_cli.py`.

<!--

If you are interested in only running results for  Gwinnett County, no further action is needed. If you are interested in running a county for which you do not have the above data, the software will notify you that the necessary data is missing.

instructions for downloading or creating these files and their formats are given here.

All file paths are given relative to the git folder for Equitable-Polling-Locations

### **datasets/census/redistricting/County_ST/DECENNIALPL2020.P3-Data.csv**:
* This is the census dataset for a racial breakdown of people of voting age by census block.
* Documentation for this dataset can be found [on the census api site for P3](https://api.census.gov/data/2010/dec/sf1/groups/P3.html)
* Instructions for downloading this data:
    * Visit [RACE FOR THE POPULATION 18 YEARS AND OVER](https://data.census.gov/table?q=P3:+RACE+FOR+THE+POPULATION+18+YEARS+AND+OVER&tid=DECENNIALPL2020.P3)
    * Select Geography:
    * Filter for Geography -> Blocks -> State -> County Name, State -> All Blocks within County Name, State
    * If asked to select table vintage, select 2020;  DEC Redistricting Data (PL-94-171)
    * Unzip and place the contents of the downloaded folder in 'datasets/census/redistricting/Count_ST/'
* Columns of P3 selected by the software:
    * White alone
    * Black or African American alone
    * American Indian And Alaska Native alone
    * Asian alone
    * Native Hawaiian and Other Pacific Islander alone
    * Some Other Race alone
    * Two or More Races

### **datasets/census/redistricting/County_ST/DECENNIALPL2020.P4-Data.csv**:
* This is the census dataset for a racial breakdown of people of voting age by census block.
* Documentation for this dataset can be found [on the census api site for P4](https://api.census.gov/data/2010/dec/sf1/groups/P4.html)
* Instructions for downloading this data:
    * Visit [HISPANIC OR LATINO, AND NOT HISPANIC OR LATINO BY RACE FOR THE POPULATION 18 YEARS AND OVER](https://data.census.gov/table?g=050XX00US13135$1000000&d=DEC+Redistricting+Data+(PL+94-171)&tid=DECENNIALPL2020.P4)
    * Select Geography:
    * Filter for Geography -> Blocks -> State -> County Name, State -> All Blocks within County Name, State
    * If asked to select table vintage, select 2020;  DEC Redistricting Data (PL-94-171)
    * Unzip and place the contents of the downloaded folder in 'datasets/census/redistricting/County_ST/'
* Columns of P4 selected by the software:
    * Total population
    * Total hispanic
    * Total non_hispanic
### **datasets/census/tiger/County_ST/tl_YYYY_FIPS_tabblockYY.shp**:
[TIGER/line Shapefiles](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html) is a database of shape files for the geographic categories used by the census.
* Documentation: https://www.census.gov/programs-surveys/geography/technical-documentation/complete-technical-documentation/tiger-geo-line/2020.html
* Instructions for downloading this data:
    * Visit https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.2020.html#list-tab-790442341
    * Scroll down to FTP Archive by State
    * Click on desired States
    * Click on desired FIPS Code for the County
    * Download tl_YYYY_FIPS_tabblockYY.zip (e.g. tl_2020_13135_tabblock20.zip)
    * Unzip and place the contents of the downloaded folder in 'datasets/census/tiger/County_ST/'
* Columns of block geography selected by the software:
    * GEOID20 - identifier. Format:1000000USFIPSCODEBLOCKNUM, e.g. 1000000US131510703153004
    * geometry - the polygon of the block
    * INTPTLAT20 - latitude of block centroid
    * INTPTLON20 - longitude of block centroid

### **datasets/census/tiger/County_ST/tl_YYYY_FIPS_bgYY.shp**:
The instructions for downloading this data is identical the instructions for the blocks with the following exception:
* Download tl_YYYY_FIPS_bgYY.zip (e.g. tl_2020_13135_bg20.zip)

-->

## Manually constructed data for historical and admissible polling locations

This is a manually constructed .csv file that contains data for existing and potential polling locations to be optimized against. In the current state, this is not on the database. Instead, it should be created locally at  `datasets/polling/County_ST/County_ST_locations_only.csv`

Example file name: datasets/polling/Gwinnett_County_GA/Gwinnett_County_GA_locations_only.csv


The columns of this data set should be named and formatted as
|Column Name | Definition | Example |
| ----- | ------ | ----- |
|Location | Name of the actual or potential polling location | 'Bethesda Senior Center' |
| Address | Street Address of the actual or potential polling location| (format flexible) '788 Hillcrest Rd NW, Lilburn, GA 20047' |
|Location Type | If polling location, must have a year when it was used | 'EV_2022_2020' or 'General_2020' or 'Primary_2022_2020_2018' or 'DropBox_2022'|
| | If potential location, has a 'location type' category and the word 'Potential' (case sensitive) | 'Community Center - Potential' |
| Lat, Lon | Comma separated concatenation of latitude and longitude (can be read off of google maps by right clicking on the location marker for the address.) | '33.964717796407434, -83.85827288222517' |

## OPTIONAL: Driving distances

If you are using driving distances (that have been calculated externally) in the optimization, place a file at `datasets/driving/County_ST/County_ST_driving_distances.csv`.  This file will only be accessed if the optional parameter 'driving' is set to True.

Example file name: datasets/driving/Gwinnett_County_GA/Gwinnett_County_GA_driving_distances.csv
The columns are as follows:
|Column Name | Definition | Example |
| ----- | ----- | ----- |
| id_orig | Census block id that matches the 'FIPSCODEBLOCKNUM' portion of the GEOID column from the file datasets/census/tiger/County_ST/tl_YYYY_FIPS_tabblockYY.shp file | 131510703153004 |
| id_dest | Name of potential polling location, as in the Location column of the file datasets/polling/County_ST/County_ST_locations_only.csv. | 'EV_2022_2020' or 'General_2020' or 'Primary_2022_2020_2018' or 'DropBox_2022' |
| distance_m | Driving distance from id_orig to id_dest in meters | 10040.72 |

