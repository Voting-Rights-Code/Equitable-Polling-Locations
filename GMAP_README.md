
# Driving Distances: OpenStreetMap vs. Google Maps

**Author:** Voting Rights Code  
**Date:** 2024-10-17  

## Overview

This project consists of two programs that compare driving distances between **Google Maps** and **OpenStreetMap (OSM)**. The aim is to identify discrepancies in driving distance calculations, especially in areas where equitable access to voting locations may be an issue.

### Program 1: Driving Distance Checker (Python)
GMAP_data.py is a program that handles data processing and calculates the difference between Google Maps and OpenStreetMap driving distances.  It depends on calling the Google Maps distance API.

### Program 2: Driving Distances Comparison Report (R/Quatro)
GMAP_distance_report.qmd is written in R using [Quatro](https://quarto.org). It produces a report that includes graphics, descriptive statistics, and tables showing discrepancies between OSM and Google Maps driving distances. It depends on local **Open Source Routing Machine** (OSRM) and **Nominatim** services for route calculation and reverse geocoding and Google Directions API for routing.

## Installation Instructions

**Note**:  all installation and operating system instructions assume a Linux operating system. 

1. **Clone The Repository**:

    ```bash
    git clone https://github.com/Voting-Rights-Code/Equitable-Polling-Locations
    ```

2. **Python Setup**:
   - Ensure you have Python 3.7+ installed.
   - Install required packages:
      + pandas
      + numpy
      + python-dotenv
      + requests

    ```bash
    pip install pandas numpy requests python-dotenv
    ```

   - The following packages are also used but typically are part of the standard library included with Python installations
      + tkinter
      + json  
      + pathlib  
      + time  
    
3. **R Setup**:
   - Install required R packages:

    ```r
    install.packages(c("data.table", "scales", "knitr", "gt", 
                        "leaflet", "osrm", "sf", "httr2", 
                        "jsonlite", "xml2", "mapsapi","ggmap"
                    ))
    ```

4.  **OSRM Servers Setup**:

    - Prerequisites
        + Make sure you have Docker installed on your machine. You can download and install Docker from [Docker's official website](https://www.docker.com/get-started).  


    1. Pull the OSRM Docker Image

        To get the latest version of the OSRM server, run the following command in your terminal:
        ```bash
            Docker pull osrm/osrm-backend:latest
        ```

    2. Download OpenStreetMap Extract

        For a selected geographic region of interest download the OpenStreetMap extract from [Geofabrik](http://download.geofabrik.de).  It is best practices to download the smallest geographic region that will service your needs as these files can be quite large and require considerable processing power to be incorporated into the servers.  

        Save the extract in a folder that you can access from a shared drive (e.g. /share).

    3. Pre-process the extract
        ```bash
        Docker run -t -v /share osrm/osrm-backend osrm-extract -p /opt/car.lua <fn>.osm.pbf
        ```
        then run:
        ```bash
        Docker run -t -v /share osrm/osrm-backend osrm-partition <fn>.osm.pbf
        Docker run -t -v /share osrm/osrm-backend osrm-customize <fn>.osm.pbf
        ```

    4. Start the Routing Engine
        ```bash
        Docker run -t -d  -i -p 5005:5000 -v /share osrm-backend osrm-routed --algorithm mld <fn>.osrm.pbf   
        ```
        It may take some time for these commands to complete.  When finished the Docker container should be running on [http://127.0.0.1:5005](http://127.0.0.1:5005).

5.  **Nominatim Servers Setup**:
    1. Pull and Initialize The Server

        These commands will download the required data, initialize the data and start the server:
        ```bash
           Docker run -it \
            -e PBF_URL=<fn>osm.pbf \
            -p 8080:8080 \
            --name nominatim \
            mediagis/nominatim:4.4
        ```
    
        **Note**:  These commands will also download and set up a Postgres server. 
    
        It may take some time for this command to complete. 

6.  ### Running The Python Script

    The python program can be run with the following command or within any IDE.

    ```bash
        python driving_distances.py
    ```

7.  ### Running The R Script

    It is recommended that RStudio IDE be used but the following will also run the program:

    ```r
        Rscript analyze_driving_distances.R
    ```
    Execution from the command line will require loading additional packages that are preinstalled in the RStudio IDE.
    
## Python Code Documentation

1. ### Google Map API Key

    The program requires an API key.  A single key (maps platform key) is used for all API calls to enabled maps libraries. The key should be stored in a file called `authentication_files` which is located in the root.  The program will automatically look for this file and privately store the key.  The file should contain a single line with the key words GMAP_Platform_Key followed bu the actual key (with no spaces):
    ```bash
        GMAP_Platform_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    ```
2. ### Selecting The Geographic Area To Be Processed

    The program should be run from the root directory.   It provides the user with an interface to select the directory containing the {location}driving_distance.csv file.

3. ### ACS Economic Data

    The program automatically reads and merges income data for the selected geographic region from the Census server.   The  fipscode and countycode values are taken from the {location}driving_distance.csv file.

4. ### Sampling 

    The purpose of the program is to create a sample from the records in /datasets/polling/{location}.csv.   The program contains a variable called `SAMPLE_ROWS` which defines the total number of records in the sample.  The program will evenly divide the total number of `SAMPLE_ROWS` into the following 4 groups (`Sample` is the variable name in the output file):
        
    1. lowest density quartile (`Sample` = 'pop')
    2. lowest percent white quartile (`Sample` = 'rac')
    3. lowest income quartile (`Sample` = 'inc')
    4. remaining dataset (`Sample` = 'oth')

    Sampling of each record is done without replacement so there is no chance of one record being in two groups.

5. ### Google Driving Distances

    The Google driving distance is calculated **only for each of the sampled records** between the origin and destination locations.   The information stored in the output file is the difference between the driving distances provided by Google and OSM:

    $$
    Program\_difference\_m = Distance _{osm}  - Distance_{gmap}
    $$

    The signed difference is stored in order to allow for future analysis of the discrepancies. 

6. ### Google Limits

    Google's Distance Matrix API has limits on the number of requests that can be made, measured in Elements Per Minute (EPM). Under the standard plan, the current limits are 100 elements per request and 1,000 elements per minute, where each element represents one origin-to-destination pair.

    In the program, there is a variable called `REQUESTS_MINUTE`, which defines the maximum number of elements that can be processed in one minute. The program pauses calls to the Distance API for one minute after processing the specified number of requests defined by `REQUESTS_MINUTE`.
    
7. ### Datasets
    
    {location} is the city/county being examined.

    - Input
        +  /datasets/driving/{location}/{location}_driving_distances.csv
            -  Contains OSM driving distances for all origin, destination pairs.  Calculated externally of these programs.  
        +  /datasets/polling/{location}/{location}.csv
            - Contains the results of the Equitable Polling Locations program.  

        Both input data sets are merged to construct the data from which the sample is extracted.

    - Output
        + /datasets/driving/{location}/{location}_compare_driving_distances.csv
            - Dataset contains the selected sample, with all data from the two input datasets plus ACS Income data and driving differences.  
        + /datasets/driving/{location}/{location}_sampling_info_driving_distances.csv
            - Contains sampling information used to the summarize the sample in the report.

## R Code Documentation

1. ### Google Map API Key

    The program requires an API key.  A single key (maps platform key) is used for all API calls to enabled maps libraries. The key should be stored in a file called `authentication_files` which is located in the root.  The exact path to the program root must be specified in the `#define data files` section of the code.   Once defined the code will automatically look for this file and privately store the key. The file should contain a single line with the key words GMAP_Platform_Key followed bu the actual key (with no spaces):
    ```bash
        GMAP_Platform_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
    ```

2. ### Output Format

    This program is written in [Quatro](https://quarto.org).   It is currently formatted to produce slides and html output.

3. ### File Location Information

    The location of the input driving directions is hardcoded in three variables defined in the program:
       
    - `root` -  full path to get to the top level of the Equitable-Polling-Locations directory.
        - e.g.: /mnt/bin/BlueBonnet/Equitable-Polling-Locations
    - `path` - path from root to get to the datasets/driving directory.
        - e.g.: datasets/driving.
    - `location` - full name of the geographic region to be read.
        - e.g.: Virginia_Beach_City_VA

    This information will likely need to be updated for each new installation. 

4. ### OSRM And Nominatim Servers

    The call to the Docker OSRM and Nominatim servers are defined as options using the variables `osrm.server` and `nominatim.server`.   Both variables are currently set to the appropriate defaults if the [Installation Instructions](#installation-instructions) were followed.  Changes will be required if other URLs or port settings are used.
`
5. ### OSRM And Nominatim Data

    The program calls the OSRM and Nominatim servers to retrieve OSM driving directions between the origin and destination locations, and to retrieve physical street addresses of these geographic locations.   
    
    Please note that the OSM distance previously calculated and stored in the driving direction input file does not match the driving distances provide by the OSRM server.   This discrepancy is visible between the data displayed in the table of extreme OSM/Google differences and the distance listed on the OSRM map.  These differences are minor, and may be due to differing OSM data files (versions), but warrant further evaluation. 

6. ### Google Map Data
    The program calls the Google maps API to retrieve driving directions between the origin and destination locations, and to retrieve distance and  physical address of the origin and destinations.  This information is used in the Google driving map. 

7. ### Google Map Tiles

    The option `GMAP_Tile` specifies if the Google driving directions are displayed on a Google Map background (True) or an OSM background (False).  Default setting is to display the map on an OSM background. 

8. ### Distance Calculation 
    The program utilizes the absolute value of the differences between the driving distances returned from each program:
 
    $$
    distance\_difference  = abs(Distance _{osm}  - Distance_{gmap})
    $$

9. ### Datasets
    
    {location} is the city/county being examined.

    - Input
      + /datasets/driving/{location}/{location}_compare_driving_distances.csv
            - Dataset contains the selected sample, with all data from the two input datasets plus ACS Income data and the driving differences.  Generated by the python program. 
        + /datasets/driving/{location}/{location}_sampling_info_driving_distances.csv
            - Contains sampling information used to the summarize the sample in the report. Generated by the python program.

    - Output
        + /GMAP_driving_distancereport.html
            - HTML file containing the output of the program including interactive maps and a link to the slides.
       + /GMAP_driving_distancereport_files
            - directory containing Quatro information necessary to produce slides and other output formats.


## Contact Information

For questions or support, contact us at: ???

## Future Work

- Resolve OSM driving differences between supplied data and OSRM results.
- Enhance visualization features with additional interactivity.
- Deeper analysis of the differences between the driving distances.
- Develop a web interface for easier access and usage.
- Combine into one program -- A design decision was made to follow the project's coding standard of data process/manipulation in Python and analysis in R.   However a single R (or Python) program can handle all the sampling, API calls, and the analysis.

## Common Issues and Troubleshooting

- **Error: API key missing**: Ensure you have set your Google Maps API key in the configuration.
- **Latency in local OSM servers**: Check the Nominatim server status and reduce the volume of requests.

- **Data File Not Found**: Ensure the paths to the data files are correct and the files exist in the specified directories.

## Changelog

- **v1.0**: Initial release with core features for constructing the data sample and producing a driving distance report.