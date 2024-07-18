import json

# Define parameters for the Amsterdam emoped simulation

params = {
# Filenames
'indir' : "INPUTS/",
'outdir' : "OUTPUTS/",
'figdir' : 'figures/',
'fn_network' : "network_lite_pt.json",
'fn_odlayer' : "od_layer.json",
'fn_transit' : "",
'fn_demand' : "demand_sample.csv",

# Vehicles speeds
#'V_CAR' : 10,
'V_BUS' : 5,
'V_TRAM' : 8,
'V_METRO' : 10,

# Transit connection (m)
'DIST_MAX' : 500,
'DIST_CONNECTION_OD' : 300,
'DIST_CONNECTION_PT' : 300,
'DIST_CONNECTION_MIX' : 300,

# Demand area
'polygon_demand' : [
    [615000, 5.813e6],
    [638000, 5.813e6],
    [638000, 5.793e6],
    [615000, 5.793e6]
]
}

with open('params.json', 'w') as f:
    json.dump(params, f, indent=4)