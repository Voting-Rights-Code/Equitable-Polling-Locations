# Equitable-Polling-Locations
Given a set of existing and candidate polling locations, output the most equitable (by Kolm-Pollack distance) set of polling locations

# To run

# Input files
### **'County_runs/County_config_DESCRIPTOR.py'**
  * Mandatory arguments
    * location: County_ST
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

### **'datasets/County_ST.csv'**: 
  * A file with a list of existing polling locations and previous polling locatons
  * Data dictionary avalalbe at
  * Instructions for creating this file available at

# Output  
