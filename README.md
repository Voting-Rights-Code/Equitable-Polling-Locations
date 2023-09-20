# Equitable-Polling-Locations
Given a set of existing and candidate polling locations, output the most equitable (by Kolm-Pollack distance) set of polling locations

# To run

# Input files
### **'County_ST_configs/County_config_DESCRIPTOR.py'**
  * Mandatory arguments
    * location: County_ST. This variable is used throughout to name files
    * year: List of years one wants to consider actual polling locations for. E.g. ['2022', '2020'] 
    * level: one of 'original', 'expanded', 'full'
      * original: Use if you just want to reassign people more optimally to existing polling locations
      * expaneded: Includes a set of identified potential polling locations. Use if you want to select a more optimal set of polling locations
      * full: Includes the cencus block group centroids. Use if you want a more ideal list of locations, for instance, to understand where to look for potential polling locations that have yet to be identified.
    * beta: In [-2, 0]. Aversion to inequality. If 0, this computes the mean distance. The further away from 0, the greater the aversion to inequality. 
    * time_limit: maximal number of minutes that the optimizer will run 
    * capacity: >= 1. A multiplicative factor that indicates how much more than *population/precincts_open* a precint is allowed to be alloted

  * Optional arguments
    * precincts_open: number of precints to be assigned. Default: number of existing polling locations
    * max_min_mult: >= 1. A scalar to limit the search radius to match polling locations. If this is too small, may not have a solution. Default: 1
    * maxpctnew = In [0,1]. The percent of new locations allowed to be matched. Default = 1 
    * minpctold = In [0,1]. The percent of existing locations allowed to be matched. Default = 0

### **'datasets/polling/Count_ST/County_ST_locations_only.csv'**: 
  * A manually constructed .csv file that contains data for existing and potential polling locations to be optimized against
  * The columns of this data set should be named and formatted as
    * Location: name of the actual or potential polling location. E.g. Lilburn Activity Builging
    * Address: Street address for the polling location. E.g. 788 Hillcrest Rd NW, Lilburn, GA 20047
    * Location type: A discription of the location. There are two types of locations
        * Previous polling locations: PollingType_YYYY. This MUST contain a list of years that the location is active. E.g. EV_2022_2020 or General_2020 or Primary_2022_2020_2018 or DropBox_2022.
        * Potential polling location: Description - Potential. This MUST contain the word 'Potential'. E.g. Community Center - Potential, Library - Potential or simply Potential
    * Lat, Long: Latitude, Longitude of the polling location (can be read off of google maps by right clicking on the location marker for the address.)
### **'datasets/census/redistricting/Count_ST/datasets/census/redistricting/Gwinnett_GA/DECENNIALPL2020.P3-Data.csv'**: 
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

### **'datasets/census/redistricting/Count_ST/datasets/census/redistricting/Gwinnett_GA/DECENNIALPL2020.P4-Data.csv'**:
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
### **'datasets/census/redistricting/Count_ST/datasets/census/tiger/Gwinnett_GA/tl_cenesusYYYY_FIPS_tablockcenesusYY.shp**:
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

### **'datasets/census/redistricting/Count_ST/datasets/census/tiger/Gwinnett_GA/tl_cenesusYYYY_FIPS_bgcenesusYY.shp**:
The instructions for downloading this data is identical the instructions for the blocks with the following exception:
* Download tl_cenesusYYYY_FIPS_bgcenesusYY.zip (e.g. tl_cenesus2020_13135_bg20.zip)

# Intermediate dataset
### **'datasets/polling/Count_ST/County_ST.csv'**: 
# Output  
