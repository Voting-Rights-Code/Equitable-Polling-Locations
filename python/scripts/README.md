# Utility Scripts

The scrips in this directory are here to assist in QC validations etc.


## Address Validator Script

The address validator takes in geocoded results from Bing and the associated addresses then queries Google to confirm the distances are within tolerance using haversine calculations. The results are written to a new CSV file.  Any addresses that exceed the threshold (currently 100 meters) get flagged with the column "within_threshold" as "False".

Note: the script will not allow you to overwrite the source file but it will allow you to overwrite any other file.  You can run the script against an already validated file to create a new/updated version of that file.  Any entries in the source CSV file with existing Google lat and lon columns will not be looked up again against the Google api, however haversine and within_threshold will be re-computed.

### Initial setup:
1. Setup a [Google Maps API key](https://developers.google.com/maps/documentation/javascript/get-api-key). (Be aware of any google charges that might incur.)
1. Copy the maps api key into a single-line file in this directory called "api.key"


### Script usage:
1. Use conda to activate equitable-polls, (instructions on how to setup equitable-polls environment can be found in the main README.md of this project repository).
2. Run the address_validator.py script and specify the source file location to validate and the output file on the command line.

Example:

```sh
conda activate equitable-polls

python -m python.scripts.address_validator datasets/driving/SC/SC_destination_latlon_from_bing.csv datasets/driving/SC/SC_destination_latlon_from_bing_validated.csv
```