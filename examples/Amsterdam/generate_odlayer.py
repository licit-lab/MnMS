# Generate an od layer matching the OD of the demand

### Imports
import os
import sys
import numpy as np
import json
import pandas as pd

sys.path.append('../../')
from mnms.graph.layers import OriginDestinationLayer
from mnms.io.graph import save_odlayer

# Files and directories
current_dir = os.getcwd()
indir = current_dir + '/inputs/'
outdir = current_dir + '/outputs/'

fn_odlayer = 'od_layer.json'

f = open('params.json')
params = json.load(f)
ams_dmd_path = indir + params['fn_demand']

# Load dmd
db_dmd = pd.read_csv(ams_dmd_path, sep=';')

nb_dmd = len(db_dmd)
origins = np.zeros((len(db_dmd),2))
destinations = np.zeros((len(db_dmd),2))
for i, row in db_dmd[:].iterrows():
    origins[i] = [float(o) for o in row['ORIGIN'].split(' ')]
    destinations[i] = [float(d) for d in row['DESTINATION'].split(' ')]

origins_str = [str(p[0]) + ',' + str(p[1]) for p in origins]
destinations_str = [str(p[0]) + ',' + str(p[1]) for p in destinations]

points_str = np.unique(origins_str + destinations_str)
points = [[float(pp) for pp in p.split(',')] for p in points_str]

# Save odlayer
odlayer = OriginDestinationLayer()

for i, od in enumerate(points):
    odlayer.create_origin_node(f"ORIGIN_{i}", od)
    odlayer.create_destination_node(f"DESTINATION_{i}", od)

save_odlayer(odlayer, indir + fn_odlayer)