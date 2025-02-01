___

<center><img src =docs\README_Image.jpg alt=logo> </center>

___

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python](https://img.shields.io/badge/python-3670A0?style=flat-square&logo=python&logoColor=ffdd54)](http://python.org)
[![R](https://img.shields.io/badge/r-%23276DC3.svg?style=flat-square&logo=r&logoColor=white)](https://www.r-project.org)
[![OSM](https://img.shields.io/badge/OSM-ffffff?logo=openstreetmap&style=flat-square&color=1f0998&logoColor=f1eeee)](https://www.openstreetmap.org)
[![Github](https://img.shields.io/badge/Github-ffffff?logo=github&style=flat-square&color=000000&logoColor=ffffff)](https://github.com/Voting-Rights-Code/Equitable-Polling-Locations)
![GitHub code size in bytes](https://img.shields.io/github/languages/code-size/Voting-Rights-Code/Equitable-Polling-Locations)
![GitHub Repo stars](https://img.shields.io/github/stars/Voting-Rights-Code/Equitable-Polling-Locations)
![GitHub watchers](https://img.shields.io/github/watchers/Voting-Rights-Code/Equitable-Polling-Locations)
![GitHub forks](https://img.shields.io/github/forks/Voting-Rights-Code/Equitable-Polling-Locations)
[![Maintenance](https://img.shields.io/badge/Maintained%3F-yes-green.svg)](https://github.com/Voting-Rights-Code/Equitable-Polling-Locations)


## Introduction 

An innovative software tool aimed at selecting an optimal set of polling sites that promote accessibility and fairness in our democratic process.  By utilizing advanced data analytics, this tool optimizes location choices to minimize travel distances for voters across communities.

## For Decision Makers

*  **Identify polling sites that enhance voter access**  
   Analyze geographic and demographic data to ensure fair distribution of polling locations, focusing on underserved populations.

* **Supports Fair Access to Polling Places**  
   By choosing polling locations that reduce distances across neighborhoods, this tool helps ensure that everyone has a fair opportunity to vote, regardless of their location within the community.

* **Data-Driven Decisions**  
   By assessing both existing and potential polling sites, this tool enables cities to locate polling places where they are most needed. It takes data from previous polling locations, available buildings, and key neighborhood centers to ensure informed, data-backed site selection.

* **Illustrative Planning Scenarios**  
   The tool provides “best case” sites by evaluating hypothetical points across communities, allowing for comparison between potential and ideal locations.

- **Configurable Requirements**: Decision makers can set requirements for existing polling site usage, maximum new sites, and other constraints to meet community goals.

## For Researchers

* **Kolm-Pollak (KP) Distance Metric**  

   The Kolm-Pollack distance is a metric used to quantify and minimize inequalities in the distribution of resources by considering both geographic and demographic factors to ensure equitable access for all individuals.
   It focuses on reducing disparities in access, aiming to improve fairness in location assignments.
   
* **Input Data and Initial Setup**  

   The approach begins by combining historical and potential polling locations with census block centroids, which represent population centers.
   
   This methodology allows for comparisons between actual and hypothetical polling site locations, enabling analysts to assess both current and proposed site distributions for accessibility and equity in resource allocation

* **Optimization Choices and Constraints**  
   Users can set optimization goals to minimize either the average distance or the KP-penalized score. Constraints can be added, such as:
   - Maximum polling locations
   - Number of new polling locations
   - Match each census block to one polling location or open precinct. 
   - User defined overcrowding limits, allowing configuration to fit community needs

* **Outputs**  
   - Matching of census blocks to polling sites, with distances and demographic data
   - Calculations of KP scores to reflect the equity balance achieved across different settings



## Further Information

For detailed guides and technical information on the **Equitable Polling Locations** software, please choose a topic from the list below: 

1. [Software Details](software.md)  

1. [Installation](to_install.md)  

1. [Running the Program](to_run.md)

1. [Database option for output storage](database.md)

1. [Input Files](input_files.md)  

1. [Output Dataset](output_datasets.md) 

1. [Intermediate Dataset](intermediate_dataset.md) 

1. [Data analytics](result_analysis.md) 

1. [Program Logging](logging.md) 

1. [References](references.md)

1. [Acknowledgements](acknowledgements.md) 

1. [How to Cite](how_to_cite.md)  


#### Need more information?  [Ask us on Discord](https://discord.com/channels/1106301559811350540/1106301560507609241)