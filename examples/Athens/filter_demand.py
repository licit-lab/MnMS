######################################################
#   Python file created par Arthur Labbaye (intern)
#
#   Creation date : octobre 2023
#
#   Description: This program aims to filter
#   requests stored in a CSV file to avoid
#   keep only relevant trips.
######################################################

import pandas as pd
import math
import geopandas as gpd

fd = "inputs/"
demand = pd.read_csv(fd+"demand.csv", sep=";")
#springs = pd.read_csv("springs.csv", header=None, names=['val'])
#deadEnds = pd.read_csv("deadEnds.csv", header=None, names=['val'])
nodes = gpd.read_file(fd+"network_data/nodes.shp")

#================================filter short trips================================
#it is useless to keep trips that are too short

distance_minimum = 1000
def calculate_distance(row):
    xo = float(row['ORIGIN'].split()[0])
    yo = float(row['ORIGIN'].split()[1])
    xd = float(row['DESTINATION'].split()[0])
    yd = float(row['DESTINATION'].split()[1])
    return math.sqrt((xd-xo)**2+(yd-yo)**2)

print(len(demand))
demand["distance"] = demand.apply(calculate_distance, axis=1)
demand = demand[demand['distance'] > distance_minimum]
demand = demand.drop('distance', axis=1)
print(len(demand))

"""
#========================filter trips too close to 'springs'========================
# 'springs' are nodes that are not accessible from another node,
# to avoid having problems I must delete the demand trips too close to these points

distance_minimum = 200

springs = springs.merge(nodes[['id', 'geometry']], left_on='val', right_on='id')
springs = springs.drop(columns=['id'])
springs['x'] = springs['geometry'].values.x
springs['y'] = springs['geometry'].values.y
springs = springs.drop('geometry', axis=1)

def calculate_distance_to_springs(row):
    x = float(row['Destination_coord'].split()[0])
    y = float(row['Destination_coord'].split()[1])
    for index, row_spring in springs.iterrows():
        x_spring = row_spring['x']
        y_spring = row_spring['y']
        distance = math.sqrt((x-x_spring)**2+(y-y_spring)**2)
        if distance < distance_minimum:
            return True
    return False

demand['Too_Close_to_Springs'] = demand.apply(calculate_distance_to_springs, axis=1)
demand= demand[~demand['Too_Close_to_Springs']]
demand = demand.drop('Too_Close_to_Springs', axis=1)

#========================filter trips too close to 'dead ends'========================
#I'm going to do the same thing to the 'springs' with the 'dead ends'

distance_minimum = 200

deadEnds = deadEnds.merge(nodes[['id', 'geometry']], left_on='val', right_on='id')
deadEnds = deadEnds.drop(columns=['id'])
deadEnds['x'] = deadEnds['geometry'].values.x
deadEnds['y'] = deadEnds['geometry'].values.y
deadEnds = deadEnds.drop('geometry', axis=1)

def calculate_distance_to_deadEnds(row):
    x = float(row['Origin_coord'].split()[0])
    y = float(row['Origin_coord'].split()[1])
    for index, row_spring in deadEnds.iterrows():
        x_spring = row_spring['x']
        y_spring = row_spring['y']
        distance = math.sqrt((x-x_spring)**2+(y-y_spring)**2)
        if distance < distance_minimum:
            return True
    return False

demand['Too_Close_to_deadEnds'] = demand.apply(calculate_distance_to_deadEnds, axis=1)
demand= demand[~demand['Too_Close_to_deadEnds']]
demand = demand.drop('Too_Close_to_deadEnds', axis=1)
print(len(demand))
"""

# save the file
demand.to_csv(fd+"demand_filtered.csv", sep=";", index=False)