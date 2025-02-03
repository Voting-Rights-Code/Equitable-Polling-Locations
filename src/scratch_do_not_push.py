from auto_generate_config import generate_configs
from utils import get_env_var_or_prompt

#Cannot get this behavior from command line
#generate_configs( 'test_configs\DeKalb_GA_no_bg_school_15.yaml_template', 'precincts_open', [11, 12, 13])

#this is fine from command line as written
#generate_configs( 'test_configs\DeKalb_GA_no_bg_school_15.yaml_template', 'precincts_open', [['2020'], ['2016', '2018'], ['2022', '2024']])

print(get_env_var_or_prompt('foo'))
