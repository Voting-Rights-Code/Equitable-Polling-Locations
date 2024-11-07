#change folder names to eliminate spaces
mv "./result_analysis" "./result_analysis"
mv "./result_analysis/map_work" "./result_analysis/map_work"

#list of locations where "County" needs to be added
declare -a add_county=("Gwinnett_GA" "DeKalb_GA" "Cobb_GA" "Berkeley_SC" "Lexington_SC" "Greenville_SC" "Richland_SC" "York_SC")

#list of locations where "County" needs to be added
declare -a change_city=("Norfolk_City_VA" "Virginia_Beach_City_VA" )


#change files manually in ., census/* and result_analysis
#for the City -> city change
#otherwise it doesn't seen the case change

for entry in "${add_county[@]}"; do
  #all but last 3 (_ST)
  County=${entry%???}
  #Just last two (ST)
  State=${entry:(-2)}
  bad_name=$entry
  good_name=$County"_County_"$State
  echo "$bad_name -> $good_name"
  ### need to do this twice to get all layers, given current structure
  for file_name in $(find . -depth -name "*$bad_name*"); do
    mv "$file_name" "${file_name/$bad_name/$good_name}"
  done

  echo "loop down a directory"
  for file_name in $(find . -depth -name "*$bad_name*"); do
    mv "$file_name" "${file_name/$bad_name/$good_name}"
  done
done

