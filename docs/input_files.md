# Input data
Before running the model, create the following:
1. A census API
1. a *manually generated* dataset of past and potential polling locations, consistent with local laws;
1.   a config file that contains the parameters for a given optimization.

Additionally,
1. if one wishes to analyze driving distances, a dataset of distances from each potential polling location to each census block group centroid.

## **Census Data (demographics and shapefiles)**:
The sofware requires a free census API key to run new counties. You can [apply on the cenus site](https://api.census.gov/data/key_signup.html) and be approved in seconds.

    1. Create the directory authentication_files/
    2. Inside authentication_files/ create a file called census_key.py
    3. The file should have a single line reading: census_key = "YOUR_KEY_VALUE"

The necessary data is automatically pulled from the census (if needed) when the model is run. However, one may also run `python -m python\utils\pull_census_data.py` to manually retrieve the data.

## Manually constructed polling locations dataset

The model optimally assigns census blocks to polling locations chosen from this predefined list. 

1. Manually create this file as a .csv with the fields indicated below.
1. Save this in the folder `datasets/polling/<Location_ST>/<Location_ST>_locations_only.csv`
    1. Example file name: datasets/polling/Gwinnett_County_GA/Gwinnett_County_GA_locations_only.csv
1. If running the model from the database, use `python -m python/scripts/db_import_locations_only_cli.py` to upload the data to the cloud.

The columns of this data set should be named and formatted as
|Column Name | Definition | Example |
| ----- | ------ | ----- |
|Location | Name of the actual or potential polling location | 'Bethesda Senior Center' |
| Address | Street Address of the actual or potential polling location| (format flexible) '788 Hillcrest Rd NW, Lilburn, GA 20047' |
|Location type | If polling location, must have a year when it was used | 'EV_2022_2020' or 'General_2020' or 'Primary_2022_2020_2018' or 'DropBox_2022'|
| | If potential location, has a 'location type' category and the word 'Potential' (case sensitive) | 'Community Center - Potential' |
| Lat, Lon | Comma separated concatenation of latitude and longitude (can be read off of google maps by right clicking on the location marker for the address.) | '33.964717796407434, -83.85827288222517' |

## Configuration files

The configuration files setting the parameters for the model runs live in `datasets/configs/config_set/`. Each file is of the form `config_name.yaml`. 

There may be multiple `config_name.yaml` files in the same `config_set` folder. However, each of these datasets can only differ from each other by a single field (aside from `config_name`, `id` and `created_at` fields). **If this property does not hold, the analysis files will not run.** 

### Creating config data
1. Create the desired `config_set` directory in `datasets/configs/`. 
1. Create a config template to generate the configuration files desired in this folder.
   1. Copy `datasets\configs\template_configs\config_template_example.yaml_template` into the folder just created
   1. Change values as needed to create the desired configurations
1. Two fields specify how the .yaml files will be created:
    1. field to vary: str; the name of the field in the config file that is allowed to vary in this config set
    1. new_range: list; the list of desired values that this field should take. Note, this can be a list of lists    
1. Run `python -m python.scripts.auto_generate_config -b 'datasets/configs/config_folder/exemplar_config.yaml_template'`

This will create a set of .yaml files in the indicaded `config_folder`, each with a different name (that is a combination of the indicated `field_to_change` and a value from the provided list.)

**Note:**
* This will also write these configs to the database.
    * Namely, if you don't have a database connection, this will not work.
* If a file by the config name already exists in the config_folder, the script will not run

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
python -m python.scripts.auto_generate_config -b 'datasets/configs/DuPage_County_IL_potential_configs/example_config.yaml_template'
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
The following fields from the PollingModelConfig class must be included in the .yaml_template file. (See `python/solver/model_config.py` for details on the class and fields). <!--In addition to the fields listed below, and `id`, and `created_at` field are generated when uploaded to the database.-->

* config_set
    * str
    * The name of the set of configs that this config belongs to.
* config_name
    * str
    * The name of this model config.
* location
    * str
    * Where the model is to be run. Usually a county level census unit. 
        * This MUST be of the form <Location>_County_ST or <Location>_city_ST, to match census encoding.
        * If it is a city within a census level county unit, see [instructions](tbd).
* census_year
    * str
    * census year that the maps and data are pulling from
* year
    * List[str],
    * An array of years of historical data relevant to this model
* bad_types
    * List[str], nullable
    * A list of location types not to be considered in this model
    * These must be selected from the `Location type`s defined in `*_locations_only.csv` file
* beta
    * float
    * level of inequality aversion: [-2,0], where 0 indicates indifference, and thus uses the mean. -1 is a good number.
* time_limit
    * ing 
    * How long the solver should try to find a solution
*  penalized_sites
    * List[str], nullable
    * A list of locations for which the preference is to only place a polling location there if absolutely necessary for coverage.
        * These must be selected from the `Location type`s defined in `*_locations_only.csv` file.  
        * A site in this list should be selected only if it improves access by x meters, where x is calculated according to the problem data. (See https://doi.org/10.48550/arXiv.2401.15452 for more information.) 
        * This option generates three additional log files: two for additional calls to the optimization solver ("...model2.log", "...model3.log") third ("...penalty.log") providing statistics related to the penalty heuristic.
* precincts_open
    * int, nullable
    * The total number of precincts to be used this year.
    * If this is null, this is calculated to be the number of
    polling places identified in the data.
* maxpctnew
    * float
    * The percent on new polling places (not already defined as a
    polling location) permitted in the data.
* minpctold
    * float
    * The minimun number of polling places (those already defined as a
    polling location) permitted in the data.
* max_min_mult
    * float
    * A multiplicative factor for the min_max distance caluclated from the data. Should be >= 1. Smaller values reduce the compute time
* capacity
    * float
    * A multiplicative factor for calculating the capacity constraint. Should be >= 1.
    * Note, if this is not paired with fixed_capacity_site_number, then the capacity changes as a function of number of precincts.
* fixed_capacity_site_number
    * int
    * The default number of open precincts if one wants to hold the number of people that can go to a location constant (as opposed to a function of the number of locations).
* driving
    * bool
    * Driving distances used if True and distance file exists in correct location
* log_distance
    * bool
    * Flag indicating whether or not the log of the distances is to be used in the optimization


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


## OPTIONAL: Driving distances

If you are using driving distances (that have been calculated externally) in the optimization, place a file at `datasets/driving/<Location>/<Location>_driving_distances.csv`.  This file will only be accessed if the optional parameter 'driving' is set to True.

Example file name: datasets/driving/Gwinnett_County_GA/Gwinnett_County_GA_driving_distances.csv
The columns are as follows:
|Column Name | Definition | Example |
| ----- | ----- | ----- |
| id_orig | Census block id that matches the 'FIPSCODEBLOCKNUM' portion of the GEOID column from the file datasets/census/tiger/County_ST/tl_YYYY_FIPS_tabblockYY.shp file | 131510703153004 |
| id_dest | Name of potential polling location, as in the Location column of the file datasets/polling/County_ST/County_ST_locations_only.csv. | 'EV_2022_2020' or 'General_2020' or 'Primary_2022_2020_2018' or 'DropBox_2022' |
| distance_m | Driving distance from id_orig to id_dest in meters | 10040.72 |

