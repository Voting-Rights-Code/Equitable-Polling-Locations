# List of features to implement
* Location preference
    1.  Implement a new objective function: (Old objective function) plus \sum weight * locations 
    1. Weight is the product of an inappropriateness score and some data derived scaling factor
    1. This may require some jiggering with how levels are done, which needs some thought of how to design/ implement.
* Integrating TargetSmart/ Catalyist geolocation of voter addresses to the main data base 
    1. Goal: to replace census derived voting age population with actual registered voters in the census block
    1. Unclear if census has just citizenship data and whether or not that would be useful
    1. Does the voter file have self reported race? If not nationally, does it have it in GA? DO NOT USE MODELED RACE FOR THIS TASK.
* Driving distance integration
    1. Currently, the model uses haversine distance
    1. Tom (Daphne's coauthor) has (opensource?) code to pull driving distances from open street map. This needs to be investigated and integrated into our system.
    1. Tom also has some papers on how well open street map covers suburban and rural US. These need to be read and understood. 
        1. Find links to said papers and put them here.
* Age and economic demographics
    1. FFA would like age and economic demographics incorporated into the inequality metrics. 
        1. Check if these are available at the block level, and if they are available for the 18+ population, or just the population as a whole. 
* Potential EV appropriateness 
    1. The rules behind what locations are legally acceptable are byzantine (to us) and vary county by county.
    1. We need someone to engage with FFA to figure out which of our selected locations are appropriate, and which are not. 
    1. Based off this information, choose more locations, or determine that there are no more appropriate locations
* Analysis for new counties
    1. FFA has given us a list of new counties that they would like to do similar analysis for. 
    1. These counties need a list of potential locations made for them that is consistent with local rules for the area.
    1. This [this drive folder](https://drive.google.com/drive/folders/1gQ2LzREbuyhiO-KhufFYiFRh47iwFJaJ?usp=drive_link) for data FFA has shared with us
* Reach out to other organizations
    1. I (we) would love to extend this work to other organizations. (NAACP TMI and CLC come to mind, and also reach out the UCSC folk to see if there is room for collaboration). This requires that we have more bandwidth/ person hours on deck to be able to manage these relationships and perform the necessary work.