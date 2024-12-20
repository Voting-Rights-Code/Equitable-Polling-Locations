for i in range(0, 31):
    with open(f'Contained_in_Madison_City_of_WI_config_driving_change_{i}.yaml', 'w') as f:
        f.write(f"""#Constants for the optimization function
location: Contained_in_Madison_City_of_WI
year: 
  - '2024'
bad_types: 
    - 'EV_2024_appointment_only'
beta: -1
time_limit: 360000 #100 hours minutes
capacity: 1.5

####Optional#####
precincts_open: null
max_min_mult: 5 #scalar >= 1
maxpctnew: {i/30:.3f} # in interval [0,1]
minpctold: 0 # in interval [0,1]
driving: True
""")
