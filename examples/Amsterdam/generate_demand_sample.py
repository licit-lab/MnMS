# Take a random sample of the demand

import numpy as np
import pandas as pd
import json

### Parameters
## Parameters file
f = open('params.json')
params = json.load(f)

fname_in = 'inputs/demand.csv'
fname_out = 'inputs/demand_sample.csv'

RATIO = 0.1
RANDOM_STATE = 79678

### Take a sample from full demand

df_agents_full = pd.read_csv(fname_in, sep=';')

weights = np.ones(len(df_agents_full))

nb_sample = int(len(df_agents_full)*RATIO)
df_agents = df_agents_full.sample(nb_sample, random_state=RANDOM_STATE, weights=weights)

df_agents.sort_values(by = 'DEPARTURE', inplace=True)
df_agents.reset_index(drop=True, inplace=True)

print('%i agents created' %(len(df_agents)))

### Save data

df_agents.to_csv(fname_out, sep = ';', index = False)