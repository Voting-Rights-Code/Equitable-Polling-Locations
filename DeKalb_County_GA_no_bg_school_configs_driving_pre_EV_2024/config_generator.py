for i in range(11, 31):
    with open(f'DeKalb_GA_no_bg_school_{i}.yaml', 'w') as f:
        f.write(f"""# Constants for the optimization function
location: DeKalb_County_GA
year:
    - '2020'
    - '2022'
bad_types: 
    - 'Elec Day School - Potential'
    - 'bg_centroid'
beta: -1
time_limit: 360000 #100 hours minutes
capacity: 5

####Optional#####
precincts_open: {i}
max_min_mult: 5 #scalar >= 1
maxpctnew: 1 # in interval [0,1]
minpctold: .75 # in interval [0,1]
driving: True
""")
