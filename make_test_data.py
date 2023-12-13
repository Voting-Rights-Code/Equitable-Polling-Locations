import pandas as pd 
from random import sample 
df = pd.read_csv('datasets/polling/Gwinnett_GA/Gwinnett_GA.csv')

#pick 10 random places of origin
random_origs = sample(list(df.id_orig.unique()), 10)

#pick 2 random centroids
random_centroids = sample(list(df[df.location_type == 'bg_centroid'].id_dest.unique()),2)


#pick 2 actual EV locations
random_polls = sample(list(df[df.dest_type == 'polling'].id_dest.unique()),2)

#pick 3 potential EV locations
random_potentials = sample(list(df[df.dest_type == 'potential'].id_dest.unique()),3)

#concatenate
random_dests = random_centroids + random_polls + random_potentials

#select these (70) rows from df
sample_df = df[df.id_orig.isin(random_origs) & df.id_dest.isin(random_dests)]

sample_df.to_csv('datasets/polling/testing/testing.csv', index = False)
