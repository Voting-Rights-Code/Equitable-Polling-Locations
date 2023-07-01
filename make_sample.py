import pandas as pd
import subprocess
import os

##set up directories####

git_dir = subprocess.Popen(['git', 'rev-parse', '--show-toplevel'], stdout=subprocess.PIPE).communicate()[0].rstrip().decode('utf-8')
data_dir = os.path.join(git_dir, 'datasets')


### Pull in salem data #### 
file_name = 'salem.csv'
file_path = os.path.join(data_dir, file_name)
df = pd.read_csv(file_path, index_col=0)
#drop duplicates
df = df.drop_duplicates()
#keep only rows with positive population
df = df[df['H7X001']>0]

#create sample set of schools, polling locations and residences
polling_locations = list(set(df[df.id_dest.str.contains('poll_2016')]['id_dest']))
schools = list(set(df[df.id_dest.str.contains('school')]['id_dest']))
residences = list(set(df['id_orig']))

polling_sample = polling_locations[:3]
school_sample = schools[:2]
dest_sample = polling_sample + school_sample
residence_sample = residences[:10]

#make sample df
sample = df.loc[df['id_orig'].isin(residence_sample) & (df['id_dest'].isin(dest_sample))]

#write sample to file
#NOTE: This doesn't quite work!
sample_path = os.path.join(data_dir, 'sample.csv')
sample.to_csv(file_path, encoding = 'utf-8', index = True)

breakpoint()

print(df.shape)
