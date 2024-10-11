import gmap_data_main
import pandas as pd
from authentication_files.file_path import gmap_csv, census_json


gmap_data = pd.read_csv(gmap_csv)
census_data = pd.read_json(census_json)

def test_main(mocker):
    mocker.patch('gmap_data_main.add_GMAP_distance_m', return_value=gmap_data)
    mocker.patch('gmap_data_main.get_census_data', return_value=census_data)
    MAIN = gmap_data_main.main()