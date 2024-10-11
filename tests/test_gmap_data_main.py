import gmap_data_main
import pandas as pd

rtn_val = pd.read_csv("gmap.csv")

def test_main(mocker):
    mocker.patch('gmap_data_main.add_GMAP_distance_m', return_value=rtn_val) 
    MAIN = gmap_data_main.main()