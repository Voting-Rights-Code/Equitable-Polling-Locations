#change folder names to eliminate spaces
mv "./result analysis" "./result_analysis"
mv "./result_analysis/map work" "./result_analysis/map_work"

#list of locations where "County" needs to be added
declare -a add_county=("Gwinnett_GA" "DeKalb_GA" "Cobb_GA" "Berkeley_SC" "Lexington_SC" "Greenville_SC" "Richland_SC" "York_SC")

#list of locations where "County" needs to be added
declare -a change_city=("Norfolk_City_VA" "Virginia_Beach_City_VA" )

for entry in "${change_city[@]}"; do
  #all but last 3 (_ST)
  County=${entry%???}
  #Just last two (ST)
  State=${entry:(-2)}
  bad_name=$entry
  good_name=${bad_name/'City'/'city'}
  echo "$bad_name -> $good_name"
  ### need to do this twice to get all layers, given current structure
  for file_name in $(find . -depth -name "*$bad_name*"); do
    temp_file=${file_name/$bad_name/"temp"} 
    new_file=${file_name/"temp"/$good_name}
    echo "Temp file name = $temp_file"
    echo "New file name = $new_file"
    mv $file_name $temp_file
    mv $temp_file $new_file
  done

  echo "loop down a directory"
  for file_name in $(find . -depth -name "*$bad_name*"); do
    new_file=${file_name/$bad_name/$good_name}
    echo "New file name = $foo"
    mv "$file_name" "$new_file"
  done
done



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

