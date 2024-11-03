#change folder names to eliminate spaces
mv "./result analysis" "./result_analysis"
mv "./result_analysis/map work" "./result_analysis/map_work"

#list of locations where "County" needs to be added
declare -a add_county=("Gwinnett_GA" "DeKalb_GA" "Cobb_GA" "Berkeley_SC" "Lexington_SC" "Greenville_SC" "Richland_SC" "York_SC")

#list of locations where "County" needs to be added
declare -a change_city=("Norfolk_City_VA" "Virginia_Beach_City_VA" )

for entry in "${add_county[@]}"
  #all but last 3 (_ST)
  County=${entry%???}
  #Just last two (ST)
  State=${entry:(-2)}
  bad_name="$entry"
  good_name="$County\_County_$State"
  echo "$bad_name -> $good_name"
  ### need to do this twice to get all layers, given current structure
  bad_name_regexp="\*$bad_name\*"
  for file_name in $(find . -depth -name $bad_name_regexp ); do
    mv "$file_name" "${file_name/$bad_name/$good_name}"
  done

  for file_name in $(find . -depth -name $good_name_regexp ); do
    mv "$file_name" "${file_name/$bad_name/$good_name}"
  done

for entry in "${change_city[@]}"
  #all but last 3 (_ST)
  County=${entry%???}
  #Just last two (ST)
  State=${entry:(-2)}
  bad_name="$entry"
  good_name="${bad_name/City/city}"
  echo "$bad_name -> $good_name"
  ### need to do this twice to get all layers, given current structure
  bad_name_regexp="\*$bad_name\*"
  for file_name in $(find . -depth -name $bad_name_regexp ); do
    mv "$file_name" "${file_name/$bad_name/$good_name}"
  done

  for file_name in $(find . -depth -name '*Cobb_GA*' ); do
    mv "$file_name" "${file_name/$bad_name/$good_name}"
  done