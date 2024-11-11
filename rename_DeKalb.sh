#just change certain DeKalb runs
for file_name in $(find "./DeKalb_County_GA_results/" "Dekalb_GA*"); do 
  echo "$file_name"
#  $bad_name="DeKalb_GA"
#  $good_name="Dekalb_County_GA" 
  mv "$file_name" "${file_name/"DeKalb_GA"/"Dekalb_County_GA" }"
done