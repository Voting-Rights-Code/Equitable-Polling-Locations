## Output datasets

For each set of parameters specified in a config file (CONFIG_FOLDER/County_config_DESCRIPTOR.yaml), the program produces 4 output files.


 1. ### *_edes.csv

    ***Demographic level ede scores*** -  For each demographic group (asian, black, hispanic, native, population, white), this table records the
    * demo_pop, the total population of that demographic in the county
    * average distance traveled by the members of that demographic: $$average\hspace{1ex}distance = weighted\hspace{1ex}distance / demo\hspace{1ex}pop$$
    * the $y_{EDE}$ for the demographic: $$y_{EDE} = \frac{-1} {( \beta * \alpha)*log(avg\hspace{1ex}KP\hspace{1ex}weight)}$$
    where $avg\hspace{1ex}KP\hspace{1ex}weight = (\sum demo\hspace{1ex}res\hspace{1ex}obj\hspace{1ex}summand)/demo\hspace{1ex}pop$

1. ### *_precinct_distances.csv
    
    Distances traveled to each precinct by demographic.  For each demographic group (asian, black, hispanic, native, population, white), and identified polling location (id_dest), this table records the

    * demo_pop, the total population of that demographic matched to that location
    * average distance traveled by the members of that demographic: $$average\hspace{1ex}distance = weighted\hspace{1ex}distance / demo\hspace{1ex}pop$$

1. ### _demographic_distances.csv

    Distances traveled by members of a census block to each polling location by demographic. This is an interim table needed to create the *_ede.csv table

    * For each demographic group (asian, black, hispanic, native, population, white), and census block (id_orig), this table records the
        * demo_pop, the total population of that demographic matched to that location
        * average distance traveled by the members of that demographic:$$average\hspace{1ex}distance = weighted\hspace{1ex}distance / demo\hspace{1ex}pop$$

1. ### *_result.csv

    A combined table of census block, matched polling location, distance, and demographic information.   This is a source table for the above three. For each census block (id_orig), this table records the

    * polling location (id_dest) to which the census block is matched
    * the distance to this polling location
    * the County_ST of the run
    * the address of the the polling location (if it exists)
    * the coordinates of the block centroid (orig_lat and orig_lon) and the coordinates of the destination (dest_lat and dest_lon)
    * population of each of the demographic groups per census block
    * It also reports weighted distance and KP factor, which are population level variables, but these columns are never used and should be removed in a future release.


## File Location

### Google Colab

If the file was run via Google Colab, the outputs are written in the folder **Colab_results/County_ST_DESCRIPTOR_result**

* The output files have the names:
    1. County_config_DESCRIPTOR_edes.csv
    1. County_config_DESCRIPTOR_precinct_distances.csv
    1. County_config_DESCRIPTOR_residence_distances.csv
    1. County_config_DESCRIPTOR_result.csv

### Command Line
* If the file was run via command line, the outputs are written in the folder **County_ST_DESCRIPTOR_result/**
    * The output files have the names:
        1. CONFIG_FOLDER.County_config_DESCRIPTOR_edes.csv
        1. CONFIG_FOLDER.County_config_DESCRIPTOR_precinct_distances.csv
        1. CONFIG_FOLDER.County_config_DESCRIPTOR_residence_distances.csv
        1. CONFIG_FOLDER.County_config_DESCRIPTOR_result.csv
