# List of features to implement

* Code base upkeep 
    1. Do we want an asana board/ some other github compatible format for this list?

* Organizational upkeep
    1. Medium post / Publicity strategy
    1. LLC
    1. Volunteer recruitiment
    1. List of forums to publicize to / org to reach out to
    1. Where do we want this to go after spring (when counties will have made their decisions about polling locations)

* Do we need a website?
    1. Investigate costing
    1. Design and make spiffy
    1. Probably too early to worry about SEO, but keep in the back of one's head.

* GUI
    1. Build a user interface for this model, maybe a jupyter notebook is sufficient?
    1. Would help with salesmanship, getting others to adopt the technology

* Figure out why some of the runs with census block group centroids are not matching all the census blocks

* Integrating TargetSmart/ Catalyist geolocation of voter addresses to the main data base 
    1. Goal: to replace census derived voting age population with actual registered voters in the census block
    1. Unclear if census has just citizenship data and whether or not that would be useful
    1. Does the voter file have self reported race? If not nationally, does it have it in GA? DO NOT USE MODELED RACE FOR THIS TASK.
    1. Questions of whether or not the errors in the voter registration files makes it dirtier than we want (e.g. people move but don't change registration, so they appear twice in the data)

* Age and economic demographics
    1. FFA would like age and economic demographics incorporated into the inequality metrics. 
        1. Check if these are available at the block level, and if they are available for the 18+ population, or just the population as a whole. 

* Reach out to other organizations
    1. I (we) would love to extend this work to other organizations. (NAACP TMI and CLC come to mind, and also reach out the UCSC folk to see if there is room for collaboration). This requires that we have more bandwidth/ person hours on deck to be able to manage these relationships and perform the necessary work.

# Features in progress
* Organizational upkeep (Susama)
    1. Public announcement / Linked In post
    1. Reaching out to other orgs
    

* Location preference
    1.  A a penalty to certain locations (Daphne Skipper)
    1. Allow the user to choose not to use certain locations (Susama Agarwala) 
    1. These need to be merged

* Preliminary analysis on distance from poll and turn out (Daniel Berger)
    1. Initial results not promising.
    1. Need a further quesion refinement from Juanma
    1. Xakota from Fair Fight is interested.

* Driving distance integration (Dan and Molly)
    1. Currently, the model uses haversine distance
    1. Need to set up a server to get Open street map data
    1. Tom also has some papers on how well open street map covers suburban and rural US. These need to be read and understood. 
        1. Find links to said papers and put them here. 

* Analysis for new counties (Susama)
    1. FFA has given us a list of new counties that they would like to do similar analysis for. 
        1. Currently Gwinnett and DeKalb are done
    1. These counties need a list of potential locations made for them that is consistent with local rules for the area.
    1. This [this drive folder](https://drive.google.com/drive/folders/1gQ2LzREbuyhiO-KhufFYiFRh47iwFJaJ?usp=drive_link) for data FFA has shared with us
# Implemented features


* Code base upkeep (Chad and Susama)
    1. Get gitlab working correctly with appropriate protections
        1. Currently no able to push to main
    1. Tagging / versioning is getting pretty urgent


* Make repo public (Chad and Susama)
    1. Fix readme / installation instructions
    1. Create testing infrastructure 
    1. Brainstorm about how to announce 
* Potential EV appropriateness 
    1. FFA has given us old polling locations which we are able to use to improve results

