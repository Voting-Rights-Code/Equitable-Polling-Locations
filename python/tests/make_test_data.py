''' A simple cli to generate test data. '''

import os
import pandas as pd
from random import sample, seed

from python.utils.directory_constants import POLLING_DIR
from .constants import TESTING_RESULTS_DIR

OUTFILE = os.path.join(TESTING_RESULTS_DIR, 'testing.csv')

#set seed
seed(157934)

df = pd.read_csv(f'{POLLING_DIR}/Gwinnett_County_GA/Gwinnett_County_GA_2020.csv')
df = df[df.population > 0 ]

#pick 10 random places of origin
random_origs = sample(list(df.id_orig.unique()), 10)

#select unique location types
unique_location_types = df['location_type'].unique()
unique_potentials = [
  loc_type for loc_type in unique_location_types
  if 'Potential' in loc_type or 'centroid' in loc_type
]

#pick 2 random locations of each type
potentials_sampled = [
  sample(list(df[df.location_type == loc_type].id_dest.unique()) , 2) for loc_type in unique_potentials
]

#flatten list
random_potentials = [loc for sampled_list in potentials_sampled for loc in sampled_list]

#pick 2 actual EV locations
random_polls = sample(list(df[df.dest_type == 'polling'].id_dest.unique()),2)

#concatenate
random_dests =  random_polls + random_potentials

#select these (70) rows from df
sample_df = df[df.id_orig.isin(random_origs) & df.id_dest.isin(random_dests)]


print(f'Writing {len(sample_df)} rows to {OUTFILE}')
sample_df.to_csv(OUTFILE, index = False)
