## Intermediate dataset

Currently, the optimizer checks for the existence of a specific dataset before running. A few notes:
* This dataset is currently created and stored locally. 
    * `datasets/polling/County_ST/County_ST.csv`
    * This will change in the future, allowing for an option for the relevant data to be saved to the database
* Currently, this dataset creates a column with the haversine distance (which is the default distance for the optimizer). 
    * In future, there will be multiple different files made, one for each type of distance studied: haversine, log haversine, driving, log driving.

### **datasets/polling/County_ST/County_ST.csv**:
This is the main data set that the optimizer uses. It includes polling locations from previous years, potential polling locations, and block group centroids, as well as distances from block centroids to the above.

Example file name: datasets/polling/Gwinett_GA/Gwinnett_GA.csv

The columns of this data set are as follows:
|Column Name | Definition | Derivation | Example / Type |
| ----- | ------ | ----- | ----- |
|Fields for matching destinations and origins|
|  |
|id_orig | Census block code | GEOID20 from block shape file | 131350501051000 |
|id_dest | Name of the actual or potential polling location | 'Location' from County_ST_location_only.csv | 'Bethesda Senior Center' |
| county | name of county and two letter state abbreviation | location from the config file | 'Gwinnett_County_GA' |
| address | If a physical polling location, street address | 'Address' from County_ST_location_only.csv  | '788 Hillcrest Rd NW, Lilburn, GA 20047'|
| | If not a physical location, name of the associated census block group | | STRING |
| dest_lat | latitude of the address or census block group centroid of the destination | google maps or INTPTLAT20 of id_dest from block group shape file| FLOAT |
| dest_lon | longitude of the address or census block group centroid of the destination | google maps or INTPTLON20 of id_dest from block group shape file| FLOAT |
| orig_lat | latitude of census block centroid of the origin | INTPTLAT20 of id_orig from block shape file| FLOAT |
| orig_lon | longitude of census block centroid of the origin | INTPTLON20 of id_orig from block shape file| FLOAT |
|location_type | A description of the id_dest location | 'Location Type' from County_ST_location_only.csv or 'bg_centroid' | 'EV_2022_2020' or 'Library - Potential' or 'bg_centroid'|
| dest_type | A coarser description of the id_dest that given in location type | Either 'polling' (if previous polling location), potential (if a building that is a potential polling location), 'bg_centroid' (if a census block centroid) |
|Distance fields|
|| 
|distance_m | distance in meters from the centroid of the block (id_orig) to id_dest | distance from (orig_lat, orig_lon) to (dest_lat, dest_lon) | FLOAT |
|source| type of distance, currently supported: (log) haversine, (log) driving | from log_distance and driving flag in config file |STRING |
|Demographic fields|
|| 
| population | total population of census block | 'P3_001N' of P3 data or 'P4_001N' of P4 data| INT |
| hispanic | total hispanic population of census block | 'P4_002N' of P4 data| INT |
| non_hispanic | total non-hispanic population of census block | 'P4_003N' of P4 data| INT |
| white | single race white population of census block | 'P3_003N' of P3 data | INT |
| black | single race black population of census block | 'P3_004N' of P3 data | INT |
| native | single race native population of census block | 'P3_005N' of P3 data | INT |
| asian | single race asian population of census block | 'P3_006N' of P3 data | INT |
| pacific_islander | single race pacific_islander population of census block | 'P3_007N' of P3 data | INT |
| multiple_races | total multi-racial population of census block | 'P3_009N' of P3 data | INT |
| other | single race other population of census block | 'P3_008N' of P3 data | INT |