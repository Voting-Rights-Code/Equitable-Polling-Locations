## Intermediate dataset

Depending on the config settings, the optimizer needs one of several different datasets that computes the distances between the census block centroids and the various possible polling locations. As these datasets are large, they is not created on the fly. Rather, the program checks for the existence of a specific dataset before running, and only creates it if it does not exsit. 

A few notes:
* The purpose of these data sets is two fold:
    * Calculate the distance (as defined by the flags in the config file) between each census block and the potential polling location
    * Merge the demographic data for each census block to the distance data 
* The data records the census year for which the blocks are drawn
* Working locally: 
    * The datasets are stored in `datasets/polling/<Location>/<Location>_(driving)_<census_year>(_log).csv`
    * The terms `log` and `driving` only appear if those flags are set to TRUE in the config file
    * The program checks if the correct file exists in the data, and creates it if it does not. 
* Working on the database:
    * This data is stored in the table `equitable-polling-locations.equitable_polling_locations_prod.polling_locations`
    * The program checks if the correct type of distance data exists in the above table and prompts the user to create and upload it if not.
        * To create and upload this dataset, run `python -m python.scripts.db_import_locations_cli `
        * This has the following parameters:
            * Census year
            * list of locations to be created
            * -t : type of distance. `linear` (default) or `log`
            * -d : map date for driving distances (if driving distances desired)

### **Distances and demographic data**:
This is the main data set that the optimizer uses. It includes polling locations from previous years, potential polling locations, and block group centroids, distances from block centroids to the above, and the demographic information for each census block.

The columns of this data set are as follows:
|Column Name | Definition | Derivation | Example / Type |
| ----- | ------ | ----- | ----- |
|Fields for matching destinations and origins|
|  |
|id_orig | Census block code | GEOID20 from block shape file | 131350501051000 |
|id_dest | Name of the actual or potential polling location | 'Location' from County_ST_location_only.csv | 'Bethesda Senior Center' |
| address | If a physical polling location, street address | 'Address' from County_ST_location_only.csv  | '788 Hillcrest Rd NW, Lilburn, GA 20047'|
| | If not a physical location, name of the associated census block group | | STRING |
| dest_lat | latitude of the address or census block group centroid of the destination | google maps latitude or INTPTLAT20 of id_dest from block group shape file| FLOAT |
| dest_lon | longitude of the address or census block group centroid of the destination | google maps longitude or INTPTLON20 of id_dest from block group shape file| FLOAT |
| orig_lat | latitude of census block centroid of the origin | INTPTLAT20 of id_orig from block shape file| FLOAT |
| orig_lon | longitude of census block centroid of the origin | INTPTLON20 of id_orig from block shape file| FLOAT |
|location_type | A description of the id_dest location | 'Location Type' from County_ST_locations_only data or 'bg_centroid' | 'EV_2022_2020' or 'Library - Potential' or 'bg_centroid'|
| dest_type | A coarser description of the id_dest that given in location type | Either 'polling' (if previous polling location), potential (if a building that is a potential polling location), 'bg_centroid' (if a census block centroid) |
|Distance fields|
|| 
|distance_m | distance in (log) meters from the centroid of the block (id_orig) to id_dest | distance from (orig_lat, orig_lon) to (dest_lat, dest_lon) | FLOAT |
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