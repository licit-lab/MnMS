############################################################
#   Python file created by Arthur Labbaye (intern)
#
#   Creation date : octobre 2023
#
#   Description: This program has the function of
#   recovering road network data from
#   shapefiles and use them to build the network
#   json adapt with the use of MnMs.
############################################################

from mnms.graph.road import RoadDescriptor
from mnms.graph.layers import MultiLayerGraph
from mnms.io.graph import save_graph
from mnms.graph.layers import CarLayer, PublicTransportLayer
from mnms.graph.zone import construct_zone_from_sections
from mnms.mobility_service.personal_vehicle import PersonalMobilityService
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.generation.layers import generate_matching_origin_destination_layer
from mnms.time import Dt, TimeTable
from mnms.vehicles.veh_type import Metro, Tram

import geopandas as gpd
import math
import pandas as pd
import os


fd = os.getcwd() + "/inputs/network_data/"

# acquisition of road data from shapefiles
data_nodes = gpd.read_file(fd+"nodes.shp")
data_sections = gpd.read_file(fd+"sections.shp")

# removal of dead end nodes to resolve 'path not found' issues
#deadEnds = pd.read_csv("../deadEnds/all.csv", header=None, names=['val'])
#data_nodes = data_nodes[~data_nodes['id'].isin(deadEnds['val'])]
#data_sections = data_sections[~data_sections['fnode'].isin(deadEnds['val'])]
#data_sections = data_sections[~data_sections['tnode'].isin(deadEnds['val'])]

# removal of sections that used these nodes (dead end)
for index, row in data_sections.iterrows():
    if math.isnan(row['fnode']) or math.isnan(row['tnode']):
        data_sections.drop(index, inplace=True)

# creatiing roads
roads = RoadDescriptor()

# creating nodes
for index, row in data_nodes.iterrows():
    node_id = int(row['id'])
    geometry = row['geometry']
    coordinates = list(geometry.coords[0])
    roads.register_node(str(node_id), coordinates)

# creating sections
for index, row in data_sections.iterrows():
    section_id = int(row['id'])
    upstream = int(row['fnode'])
    downstream = int(row['tnode'])
    roads.register_section(str(section_id), str(upstream), str(downstream))

# creating car layer
car_service = PersonalMobilityService()
car_layer = CarLayer(roads, default_speed=7, services=[car_service])

for index, row in data_nodes.iterrows():
    node_id = int(row['id'])
    car_layer.create_node(str(node_id), str(node_id))

for index, row in data_sections.iterrows():
    section_id = int(row['id'])
    upstream = int(row['fnode'])
    downstream = int(row['tnode'])
    car_layer.create_link(str(section_id), str(upstream), str(downstream), {}, [str(section_id)])

# creating zone
res = construct_zone_from_sections(roads, "RES", roads.sections)
roads.add_zone(res)

# cconstruction of the graph
odlayer = generate_matching_origin_destination_layer(roads)
mlgraph = MultiLayerGraph([car_layer],odlayer,0.001)

# save the graph
graph_file = 'inputs/mlgraph_car.json'
save_graph(mlgraph, graph_file)
