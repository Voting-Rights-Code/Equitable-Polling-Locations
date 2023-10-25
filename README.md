# Equitable-Polling-Locations
Given a set of existing and candidate polling locations, output the most equitable (by Kolm-Pollak distance) set of polling locations. The outputs of this model can be used to measure inequity among different racial groups in terms of access to polls (measured solely in terms of distance) and investigate how changes in choices and number of polling locations would change these inequities. 

The algorithm for this model is as follows:
1. Create a list of potential polling locations
    1. Start with a list of historical polling locations 
    1. Add to this a list of  buildings where one would like to have future polling locations
    1. Combine this data with a list of "best case scenario" polling locations, modeled by census block group centroids
1. Compute the distance from the centroid of each census block to the potential polling location (building or best case scenario)
    1. We average over census block group rather than individual houses for computational feasibilty.
1. Compute the Kolm-Pollack weight from each block group to each polling location
    1. KP_factor  = e^(- beta* alpha * distance)
        1. beta is a user defined parameter
        1. alpha is a data derived normalization factor (alpha = \sum (population * distance_to_closest_poll^2))
    1. The KP_factor plays the role of a weighted distance in a standard objective function.
        1. The exponential in the KP_factor penalizes inequliaty in distances traveled
        1. For instance a group of 5 people all having to travel 1 mile to a polling location would have a lower KP_factor than a situation where 4 people travel 1/2 a mile while the fifth travels 3, even though the average distance traveled in both cases is the same.
1. Choose whether to minimize the average distance or the inequity penalized score (y_EDE) in the model 
    1. Set beta = 0 for average distance
        1. In this case, minimize the average distance traveled
    1. Set beta in [-2, 0) for the inequity penalized score (y_EDE). The lower the beta, the greater penalty to inequality
        1. In this case, minimize (\sum block population * KP_factor)/ county population
1. Minimize the above according to the following constraints:
    1. Can only have a user specified number of polling locations open
    1. A user defined bound on the number of new locations
        1. Some maximal percent allowed to be new
        1. Some minimal percent that must have been a polling location in the past
        1. This can be easily modified to accomodate other needs 
    1. Each census block can only be matched to one polling location
    1. Each census block must be matched to a single open precinct
    1. A user defined overcrowding contstraint
1. The model returns a list of matchings between census blocks and polling locations, along with the distance between the two, and a demographic breakdown of the population. 
1. The model then uses this matching and demographic data to compute a new data derived scaling factor (alpha), which it then uses to compute the inequity penalized score (y_EDE) for the matched system.

# To install
1. Clone main branch of Equitable-Polling-Locations
1. Install conda if you do not have it already
    1. This program uses SCIP as an optimizer, which is easily installed using Conda, but not using pip.
    1. If you do not have conda installed already, use the relevant instructions [here] (https://conda.io/projects/conda/en/latest/user-guide/install/index.html)
1. Create and activate conda environment. (Note, on a Windows machine, this requires using Anaconda Prompt.)
    1. `$ conda create --name equitable-polls `
    1. `$ conda activate equitable-polls`
1. Install requirements.txt
    1. Change directory to git repo
    1. `$ conda install --file requirements.txt`

# To run
From command line:
* In the directory of the Equitable-Polling-Locations git repo:
    * python ./model_run_cli.py -cNUM -lLOG_FILE ./path/to/config/file.yaml
        * NUM = number of cores to use for simulatneous runs (reccommend <=4 for most laptops)
        * LOG_FILE = Where to put log file. Must exist, or will not run
        * path to config file accepts wild cards to set of sequential runs

From Google Colab:
* For example, follog the the instructions in [this file](./Colab_runs/colab_Gwinnett_expanded_multi_11_12_13_14_15.ipynb) (To be accessed in the directory of the Equitable-Polling-Locations git repo)
# Input files
There are six files needed to run this program. Instructions for downloading these files and their formats are given here.

* There are 4 files from the census needed for each county:
    * block level P3 data for a county (racial breakdown of voting age population)
    * block level P4 data for a county (ethnicity breakdown of voting age population)
    * block shape files
    * block group shape files
* There is one manually generated file for each county
    * previous and potential polling locations for a country
* There is one config file needed as an argument to run this file

NOTE: 
1. Currently, this model is run on census data, which counts voting age population. We make no assumptions about elligibility to vote, either in terms of citizenship, local disqualification laws or voter registration status.
2. Ethnicity (Hispanic / Non-Hispanic) is orthogonal to race in the census data. Therefore, one may be Hispanic and Asian at the same time.

All file paths are given relative to the git folder for Equitable-Polling-Locations

### **datasets/census/redistricting/County_ST/datasets/census/redistricting/County_ST/DECENNIALPL2020.P3-Data.csv**: 
* This is the census dataset for a racial breakdown of people of voting age by census block.
* Documentation for this dataset can be found [on the census api site for P3](https://api.census.gov/data/2010/dec/sf1/groups/P3.html)
* Instructions for downloading this data:
    * Visit [RACE FOR THE POPULATION 18 YEARS AND OVER](https://data.census.gov/table?q=P3:+RACE+FOR+THE+POPULATION+18+YEARS+AND+OVER&tid=DECENNIALPL2020.P3)
    * Select Geography:
    * Filter for Geography -> Blocks -> State -> County Name, State -> All Blocks within County Name, State
    * If asked to select table vintage, select 2020;  DEC Redistricting Data (PL-94-171)
    * Unzip and place the contents of the dowloaded folder in 'datasets/census/redistricting/Count_ST/datasets/census/redistricting/Gwinnett_GA/'
* Colums we want from P3:
    * White alone
    * Black or African American alone
    * American Indian And Alaska Native alone
    * Asian alone
    * Native Hawaiian and Other Pacific Islander alone
    * Some Other Race alone
    * Two or More Races

### **datasets/census/redistricting/County_ST/datasets/census/redistricting/County_ST/DECENNIALPL2020.P4-Data.csv**:
* This is the census dataset for a racial breakdown of people of voting age by census block.
* Documentation for this dataset can be found [on the census api site for P4](https://api.census.gov/data/2010/dec/sf1/groups/P4.html)
* Instructions for downloading this data:
    * Visit [HISPANIC OR LATINO, AND NOT HISPANIC OR LATINO BY RACE FOR THE POPULATION 18 YEARS AND OVER](https://data.census.gov/table?g=050XX00US13135$1000000&d=DEC+Redistricting+Data+(PL+94-171)&tid=DECENNIALPL2020.P4)
    * Select Geography:
    * Filter for Geography -> Blocks -> State -> County Name, State -> All Blocks within County Name, State
    * If asked to select table vintage, select 2020;  DEC Redistricting Data (PL-94-171)
    * Unzip and place the contents of the dowloaded folder in 'datasets/census/redistricting/County_ST/datasets/census/redistricting/County_ST/'
* Columns used from P4:
    * Total population
    * Total hispanic
    * Total non-hispanic
### **datasets/census/redistricting/County_ST/datasets/census/tiger/County_ST/tl_cenesusYYYY_FIPS_tablockcenesusYY.shp**:
[TIGER/line Shapefiles](https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.html) is a database of shape files for the geographic categories used by the census.  
* Documentation: https://www.census.gov/programs-surveys/geography/technical-documentation/complete-technical-documentation/tiger-geo-line/2020.html
* Instuction for downloading this data:
    * Visit https://www.census.gov/geographies/mapping-files/time-series/geo/tiger-line-file.2020.html#list-tab-790442341
    * Scroll down to FTP Archiv by State
    * Click on desired States
    * Click on desired FIPS Code for the County
    * Download tl_cenesusYYYY_FIPS_tablockcenesusYY.zip (e.g. tl_cenesus2020_13135_tablock20.zip)
    * Unzip and place the contents of the dowloaded folder in 'datasets/census/redistricting/County_ST/datasets/census/tiger/County_GA/'
* Columns we want from blocks:
    * GEOID20 - identifier. Format:1000000USFIPSCODEBLOCKNUM, e.g. 1000000US131510703153004
    * geometry - the polygon of the block
    * INTPTLAT20 - latitude of block centroid
    * INTPTLON20 - longitude of block centroid

### **datasets/census/redistricting/County_ST/datasets/census/tiger/County_ST/tl_cenesusYYYY_FIPS_bgcenesusYY.shp**:
The instructions for downloading this data is identical the instructions for the blocks with the following exception:
* Download tl_cenesusYYYY_FIPS_bgcenesusYY.zip (e.g. tl_cenesus2020_13135_bg20.zip)

### **datasets/polling/County_ST/County_ST_locations_only.csv**: 
This is a manually constructed .csv file that contains data for existing and potential polling locations to be optimized against
Example file name: datasets/polling/Gwinnett_GA/Gwinnett_GA_locations_only.csv
The columns of this data set should be named and formatted as
|Column Name | Definition | Example |
| ----- | ------ | ----- |
|Location | Name of the actual or potential polling location | 'Bethesda Senior Center' |
| ----- | ------ | ----- |
| Address | Street Address of the actual or potential polling location| (format flexible) '788 Hillcrest Rd NW, Lilburn, GA 20047' |
| ----- | ------ | ----- |
|Location Type | If polling location, must have a year when it was used | 'EV_2022_2020' or 'General_2020' or 'Primary_2022_2020_2018' or 'DropBox_2022'|
| ----- | ------ | ----- |
| | If potential location, has a 'location type' category and the word 'Potential' (case sensitive) | 'Community Center - Potential' | 
| ----- | ------ | ----- |
| Lat, Long | Comma separated concatenation of latitude and longitude (can be read off of google maps by right clicking on the location marker for the address.) | '33.964717796407434, -83.85827288222517' |
| ----- | ------ | ----- |

### **CONFIG_FOLDER/County_config_DESCRIPTOR.yaml**
These are the config files for the various runs.
Example path Gwinnett_GA_configs/Gwinnett_config_full_11.yaml
  * Mandatory arguments
    * location: County_ST. This variable is used throughout to name files
    * year: List of years one wants to consider actual polling locations for. E.g. ['2022', '2020'] 
    * level: one of 'original', 'expanded', 'full'
      * original: Use if you just want to reassign people more optimally to existing polling locations
      * expanded: Includes a set of identified potential polling locations. Use if you want to select a more optimal set of polling locations
      * full: Includes the cencus block group centroids. Use if you want a more ideal list of locations, for instance, to understand where to look for potential polling locations that have yet to be identified.
    * beta: In [-2, 0]. Aversion to inequality. If 0, this computes the mean distance. The further away from 0, the greater the aversion to inequality. 
    * time_limit: maximal number of minutes that the optimizer will run 
    * capacity: >= 1. A multiplicative factor that indicates how much more than *population/precincts_open* a precint is allowed to be alloted

  * Optional arguments
    * precincts_open: number of precints to be assigned. Default: number of existing polling locations
    * max_min_mult: >= 1. A scalar to limit the search radius to match polling locations. If this is too small, may not have a solution. Default: 1
    * maxpctnew = In [0,1]. The percent of new locations allowed to be matched. Default = 1 
    * minpctold = In [0,1]. The percent of existing locations allowed to be matched. Default = 0

# Intermediate dataset

### **datasets/polling/County_ST/County_ST.csv**: 
This is the main data set that the optimizer uses. It includes polling locations from previous years, potential polling locations, and block group centroids, as well as distances from block centroids to the above.
Example file name: datasets/polling/Gwinett_GA/Gwinnett_GA.csv

The columns of this data set are as follows:
|Column Name | Definition | Derivation | Example / Type |
| ----- | ------ | ----- | ----- |
|id_orig | Census block code | GEOID20 from block shape file | 131350501051000 |
| ----- | ------ | ----- | ----- |
|id_dest | Name of the actual or potential polling location | 'Location' from County_ST_location_only.csv | 'Bethesda Senior Center' |
| ----- | ------ | ----- | ----- |
| | Census block group code | GEOID20 from block group shape file | 131350501051 |
| ----- | ------ | ----- | ----- |
| distance_m | distance in meters from the centroid of the block (id_orig) to id_dest | haversine distance from (orig_lat, orig_lon) to (dest_lat, dest_lon) | FLOAT |
| ----- | ------ | ----- | ----- |
| county | name of county and two letter state abbreviation | location from the config file | 'Gwinnett_GA' | 
| ----- | ------ | ----- | ----- |
| Address | If a physical polling location, street address | 'Address' from County_ST_location_only.csv  | '788 Hillcrest Rd NW, Lilburn, GA 20047'|
| ----- | ------ | ----- | ----- |
| | If not a potential coordinate, name of the assocaited census block group |  | NA |
| ----- | ------ | ----- | ----- |
| dest_lat | lattitude of the address or census block group centroid of the destination | google maps or INTPTLAT20 of id_dest from block group shape file| FLOAT |
| ----- | ------ | ----- | ----- |
| dest_lon | longitude of the address or census block group centroid of the destination | google maps or INTPTLON20 of id_dest from block group shape file| FLOAT |
| ----- | ------ | ----- | ----- |
| orig_lat | lattitude of census block centroid of the origin | INTPTLAT20 of id_orig from block shape file| FLOAT |
| ----- | ------ | ----- | ----- |
| orig_lon | longitude of census block centroid of the origin | INTPTLON20 of id_orig from block shape file| FLOAT |
| ----- | ------ | ----- | ----- |
|location_type | A description of the id_dest location | 'Location Type' from County_ST_location_only.csv or 'bg_centroid' | 'EV_2022_2020' or 'Library - Potential' or 'bg_centroid'|
| ----- | ------ | ----- | ----- |
| dest_type | A coarser desription of the id_dest that given in location type | Either 'polling' (if previous polling location), potential (if a building that is a potential polling location), 'bg_centroid' (if a census block centroid) |
| ----- | ------ | ----- | ----- |
| population | total population of census block | 'P3_001N' of P3 data or 'P4_001N' of P4 data| INT |
| ----- | ------ | ----- | ----- |
| hispanic | total hispanic population of census block | 'P4_002N' of P4 data| INT |
| ----- | ------ | ----- | ----- |
| non-hispanic | total non-hispanic population of census block | 'P4_003N' of P4 data| INT | 
| ----- | ------ | ----- | ----- |
| white | single race white population of census block | 'P3_003N' of P3 data | INT |
| ----- | ------ | ----- | ----- |
| black | single race black population of census block | 'P3_004N' of P3 data | INT |
| ----- | ------ | ----- | ----- |
| native | single race native population of census block | 'P3_005N' of P3 data | INT |
| ----- | ------ | ----- | ----- |
| asian | single race asian population of census block | 'P3_006N' of P3 data | INT |
| ----- | ------ | ----- | ----- |
| pacific_islaner | single race pacific_islander population of census block | 'P3_007N' of P3 data | INT |
| ----- | ------ | ----- | ----- |
| other | single race other population of census block | 'P3_008N' of P3 data | INT |
| ----- | ------ | ----- | ----- |
| multiple_races | total multi-racial population of census block | 'P3_009N' of P3 data | INT | 
| ----- | ------ | ----- | ----- |
# Output datasets

For each set of parameters specified in a config file (CONFIG_FOLDER/County_config_DESCRIPTOR.yaml), the program produces 4 output files.
* If the file was run via Google Colab, the outputs are written in the folder Colab_results/County_ST_DESCRIPTOR_result
    * The output files have the names:
        * County_config_DESCRIPTOR_edes.csv
        * County_config_DESCRIPTOR_precinct_distances.csv
        * County_config_DESCRIPTOR_residence_distances.csv
        * County_config_DESCRIPTOR_result.csv

* If the file was run via command line, the outputs are written in the folder Gwinnett_GA_results/
    * The output files have the names:
        * CONFIG_FOLDER.County_config_DESCRIPTOR_edes.csv
        * CONFIG_FOLDER.County_config_DESCRIPTOR_precinct_distances.csv
        * CONFIG_FOLDER.County_config_DESCRIPTOR_residence_distances.csv
        * CONFIG_FOLDER.County_config_DESCRIPTOR_result.csv

The four files can be described as follow:
* *_edes.csv (demographic level ede scores)
    * For each demographic group (asian, black, hispanic, native, population, white), this table records the 
        * demo_pop, the total population of that demographic in the county
        * average distance traveled by the members of that demographic: average_distance = weighted_distance / demo_pop
        * the y_EDE for the demographic: y_EDE = -1/(beta * alpha)*log(avg_KP_weight) 
            * where avg_KP_weight= (\sum demo_res_obj_summand)/demo_pop
* *_precinct_distances.csv (distances traveled to each precint by demographic)
    * For each demographic group (asian, black, hispanic, native, population, white), and identified polling location (id_dest), this table records the 
        * demo_pop, the total population of that demographic matched to that location
        * average distance traveled by the members of that demographic: average_distance = weighted_distance / demo_pop
* *_demographic_distances.csv (distances traveled by members of a census block to each polling loction by demographic)
    * This is an interim table needed to create the *_ede.csv table
    * For each demographic group (asian, black, hispanic, native, population, white), and census block (id_orig), this table records the 
        * demo_pop, the total population of that demographic matched to that location
        * average distance traveled by the members of that demographic: average_distance = weighted_distance / demo_pop
* *_result.csv (a combined table of census block, matched pollig location, distance, and demographic information)
    * This is a source table for the above three
    * For each census block (id_orig), this table records the
        * polling location (id_dest) to which the census block is matched
        * the distance to this polling location
        * The County_ST of the run
        * the address of the the polling location (if it exists)
        * the coordinates of the block centroid (orig_lat and orig_lon) and the coordinates of the destination (dest_lat and dest_lon)
        * population of each of the demographic groups per census block
        * It also reports weighted distance and KP factor, which are population level variables, but these columns are never used and should be removed in a future release.