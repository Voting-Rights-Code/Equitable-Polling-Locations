import pandas as pd
import subprocess
import os

##set up directories####

git_dir = subprocess.Popen(['git', 'rev-parse', '--show-toplevel'], stdout=subprocess.PIPE).communicate()[0].rstrip().decode('utf-8')
data_dir = os.path.join(git_dir, 'datasets')


### Pull in salem data #### 
file_name = 'Gwinnett_GA.csv'
file_path = os.path.join(data_dir, file_name)
df = pd.read_csv(file_path, index_col=0)
#drop duplicates
df = df.drop_duplicates()
#keep only rows with positive population
df = df[df['population']>0]

#create sample set of schools, polling locations and residences
polling_locations = list(set(df[df.dest_type == 'polling']['id_dest']))
schools = list(set(df[df.dest_type == 'potential']['id_dest']))
residences = list(set(df['id_orig']))

polling_sample = polling_locations[:3]
school_sample = schools[:2]
dest_sample = polling_sample + school_sample
residence_sample = residences[:10]

#make sample df
sample = df.loc[df['id_orig'].isin(residence_sample) & (df['id_dest'].isin(dest_sample))]

#write sample to file
#NOTE: This doesn't quite work!
sample_path = os.path.join(data_dir, 'sample_Gwinnett.csv')
sample.to_csv(sample_path, encoding = 'utf-8', index = True)



print(df.shape)
