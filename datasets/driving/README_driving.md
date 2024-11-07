# Driving distances

## Input file formats

Input is two files: origins and destinations. Each of these is a "location file". Location files can either specify 1. addresses or 2. lat/lon coordinates. The required columns for each is as follows:

   1. 'id', 'address', 'city', 'state'
   2. 'id', 'lat', 'lon'


- Additional columns are fine to include, as long as the required columns are included and accurately named. 
- There is no need to indicate (apart from the column names) which kind of location file it is.
- **Examples:**
    - "lat/lon" location file examples are in 'datasets/driving/Gwinnett_County_GA'
    - an "address" location file example is in 'datasets/driving/SC'

## Output file formats

Output is 3 files:

1. name_driving_distances.csv: 'orig_id', 'dest_id', 'distance'
2. two files of the form:
   - locationfilename_out.csv: 'id', 'ors_lat', 'ors_lon'

The 'ors_lat' and 'ors_lon' are the actual latitude and longitude used by the Open Route Service (ORS) in the distance calculation. This is not always the same as the latitude and longitude in the input files: the ORS "snaps" to the closest mappable location from a given input location.

- **Examples:**
    - Examples of the output files are in 'datasets/driving/Gwinnett_County_GA/'