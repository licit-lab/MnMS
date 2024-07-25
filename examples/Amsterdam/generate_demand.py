# Generate a synthetic demand based on city of Amsterdam data

import numpy as np
import pandas as pd
import json
from mnms.tools.geometry import points_in_polygon

### Parameters
## Parameters file
f = open('params.json')
params = json.load(f)

fname_in = 'inputs/demand_city_hex_9.csv'
fname_out = 'inputs/demand.csv'
T_START = 16*3600 # has to be consistent with the PEAK choice
T_END = 18*3600
PEAK = 'AS' # OS, AS, RD -> 7-9/16-18/off
MODES = ['OV'] # PA, OV, FI -> car, PT, bike

labels = [mode+PEAK+'_trips' for mode in MODES]

polygon = np.asarray(params['polygon_demand'])
DIST_MIN = 5e2 # m

RANDOM_STATE = 79678

df_dmd_all = pd.read_csv(fname_in, sep=',')
print(sum([df_dmd_all[label].sum() for label in labels]))
#df_dmd = df_dmd_all
### Filter demand

# select O/D in polygon
pts_o = list(df_dmd_all.O_hex_xy.apply(lambda x: [float(y) for y in x[1:-1].split(', ')]))
pts_d = list(df_dmd_all.D_hex_xy.apply(lambda x: [float(y) for y in x[1:-1].split(', ')]))
mask_o = points_in_polygon(polygon, pts_o)
mask_d = points_in_polygon(polygon, pts_d)
df_dmd = df_dmd_all[mask_o & mask_d]
print(sum([df_dmd[label].sum() for label in labels]))

# remove small dist
pts_o = list(df_dmd.O_hex_xy.apply(lambda x: [float(y) for y in x[1:-1].split(', ')]))
pts_d = list(df_dmd.D_hex_xy.apply(lambda x: [float(y) for y in x[1:-1].split(', ')]))
dist = [np.sqrt((o[0]-d[0])**2 + (o[1]-d[1])**2) for o,d in zip(pts_o, pts_d)]
mask_dist = [d>=DIST_MIN for d in dist]
df_dmd = df_dmd[mask_dist]
print(sum([df_dmd[label].sum() for label in labels]))

# remove empty od
mask = df_dmd.apply(lambda row: np.asarray([row[label]!=0 for label in labels]).any(), axis=1)
df_dmd = df_dmd[mask]
df_dmd.reset_index(drop=True, inplace=True)
print(sum([df_dmd[label].sum() for label in labels]))

### Generate agents

np.random.seed(seed=RANDOM_STATE)

agents_id = []
agents_o = []
agents_d = []
agents_dept_time = []
i_agent=1
for i, row in df_dmd.iterrows():
    o = row['O_hex_xy'][1:-1].replace(',','')
    d = row['D_hex_xy'][1:-1].replace(',','')
    # nb_dmd = int(row[labels].sum()+0.5)
    nb_dmd = int(row[labels].sum())
    if np.random.random() <= row[labels].sum() - nb_dmd:
        nb_dmd += 1
    for _ in range(nb_dmd):
        td = T_START + np.random.random()*(T_END-T_START)
        td_str = '%02i:%02i:%02i' %(td/3600, np.remainder(td,3600)/60, np.remainder(td,60))

        agents_id.append(i_agent)
        agents_o.append(o)
        agents_d.append(d)
        agents_dept_time.append(td_str)
        i_agent += 1

df_agents = pd.DataFrame({'ID': agents_id, 'DEPARTURE':agents_dept_time,
                          'ORIGIN':agents_o, 'DESTINATION':agents_d})

df_agents.sort_values(by='DEPARTURE', inplace=True)

print('%i agents created from a demand of %.2f' %(len(df_agents), sum([df_dmd[label].sum() for label in labels])))

### Save data

df_agents.to_csv(fname_out, sep = ';', index = False)