## Input files

There are six files needed to run this program. 

* There are 4 files from the census needed for each county, These are pulled from the census the first time a county is run:

    1. block level P3 data for a county (racial breakdown of voting age population)

    1. block level P4 data for a county (ethnicity breakdown of voting age population)

    1. block shape files

    1. block group shape files

* There is one *manually generated* file for each county:

    - previous and potential polling locations for a country

* There is one config file needed as an argument to run the program

## Census Data (demographics and Shapefiles)

The software requires a free census API key to run new counties. You can [apply on the census site](https://api.census.gov/data/key_signup.html) and be approved in seconds. Then

1. Create the directory authentication_documents/ 

1. Inside authentication_documents/ create a file called census_key.py

1. The file should have a single line reading: census_key = "YOUR_KEY_VALUE"

If you are only running counties already in the repo you can use the empty string for your key (census_key = "") but the censu_key.py file must still exist locally.

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
    * Total non-hispanic
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

## Data 

### datasets/polling/County_ST/County_ST_locations_only.csv

This is a manually constructed .csv file that contains data for existing and potential polling locations to be optimized against

Example file name: datasets/polling/Gwinnett_GA/Gwinnett_GA_locations_only.csv
The columns of this data set should be named and formatted as

|Column Name | Definition | Example |
| ----- | ------ | ----- |
|Location | Name of the actual or potential polling location | 'Bethesda Senior Center' |
| Address | Street Address of the actual or potential polling location| (format flexible) '788 Hillcrest Rd NW, Lilburn, GA 20047' |
|Location Type | If polling location, must have a year when it was used | 'EV_2022_2020' or 'General_2020' or 'Primary_2022_2020_2018' or 'DropBox_2022'|
| | If potential location, has a 'location type' category and the word 'Potential' (case sensitive) | 'Community Center - Potential' |
| Lat, Long | Comma separated concatenation of latitude and longitude (can be read off of google maps by right clicking on the location marker for the address.) | '33.964717796407434, -83.85827288222517' |

### datasets/driving/County_ST/County_ST_driving_distances.csv

OPTIONAL file for using driving distances (that have been calculated externally) in the optimization. This file will only be accessed if the optional parameter 'driving' is set to True.
Example file name: datasets/driving/Gwinnett_GA/Gwinnett_GA_driving_distances.csv
The columns are as follows:
|Column Name | Definition | Example |
| ----- | ----- | ----- |
| id_orig | Census block id that matches the 'FIPSCODEBLOCKNUM' portion of the GEOID column from the file datasets/census/tiger/County_ST/tl_YYYY_FIPS_tabblockYY.shp file | 131510703153004 |
| id_dest | Name of potential polling location, as in the Location column of the file datasets/polling/County_ST/County_ST_locations_only.csv. | 'EV_2022_2020' or 'General_2020' or 'Primary_2022_2020_2018' or 'DropBox_2022' |
| distance_m | Driving distance from id_orig to id_dest in meters | 10040.72 |

### **CONFIG_FOLDER/County_config_DESCRIPTOR.yaml**
These are the config files for the various runs.

Example path: Gwinnett_GA_configs/Gwinnett_config_full_11.yaml

Recommended convention: Each config folder should only have one parameter changing. For example, DeKalb_GA_no_bg_school_config should contain only (and all) runs with block groups and schools in the bad list, changing only the number of desired polling locations
  * Mandatory arguments
    
    * location: County_ST. This variable is used throughout to name files
    
    * year: List of years one wants to consider actual polling locations for. E.g. ['2022', '2020']
    
    * bad_types: List of location types not to be considered in this model.
        * E.g. ['Election Day Loc - Potential', 'bg_centroid' ]   
        * Must be labels already existing in the data
   
    * beta: In [-2, 0]. Aversion to inequality. If 0, this computes the mean distance. The further away from 0, the greater the aversion to inequality.
   
    * time_limit: maximal number of minutes that the optimizer will run
   
    * capacity: >= 1. A multiplicative factor that indicates how much more than *population/precincts_open* a precinct is allowed to be allotted

  * Optional arguments
    * precincts_open: number of precincts to be assigned. Default: number of existing polling locations

    * max_min_mult: >= 1. A scalar to limit the search radius to match polling locations. If this is too small, the optimizer may not find a solution. Default: 1
   
    * maxpctnew = In [0,1]. The percent of new locations allowed to be matched. Default = 1
  
    * minpctold = In [0,1]. The percent of existing locations allowed to be matched. Default = 0
  
    * penalized_sites: List of potential polling locations (subset of those considered in run) that are less desireable. A site in this list should be selected only if it improves access by x meters, where x is calculated according to the problem data. (See https://doi.org/10.48550/arXiv.2401.15452 for more information.) This option generates three additional log files: two for additional calls to the optimization solver ("...model2.log", "...model3.log") third ("...penalty.log") providing statistics related to the penalty heuristic.
   
    * driving = In [True,False]. If True, then driving distances (versus straight-line/Haversine distances) are used. This option requires driving distances in the datasets folder as described above. Default = False