# Build MnMS network/graph based on road network and metro/tram data

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

# Parameters
METRO_SPEED = 11 # m/s
METRO_HEADTIME = 5 #min
TRAM_SPEED = 10 # m/s
TRAM_HEADTIME = 10 #min

fd = os.getcwd() + "/inputs/network_data/"

# acquisition of road data from shapefiles
data_nodes = gpd.read_file(fd+"nodes.shp")
data_sections = gpd.read_file(fd+"sections.shp")

# removal of dead end nodes to resolve 'path not found' issues
deadEnds = pd.read_csv(fd+"useless_nodes.csv", header=None, names=['val'])
data_nodes = data_nodes[~data_nodes['id'].isin(deadEnds['val'])]
data_sections = data_sections[~data_sections['fnode'].isin(deadEnds['val'])]
data_sections = data_sections[~data_sections['tnode'].isin(deadEnds['val'])]

# removal of sections that used these nodes (dead end)
for index, row in data_sections.iterrows():
    if math.isnan(row['fnode']) or math.isnan(row['tnode']):
        data_sections.drop(index, inplace=True)

# acquisition and formatting of tram and metro data from shapefiles
stations = gpd.read_file(fd + "Stations_0/Stations_0_5yL8s1R.shp", encoding='utf-8')
stations.crs = 'EPSG:2100'
stations = stations.to_crs('EPSG:32234')
stations['x'] = stations['geometry'].apply(lambda geom: geom.centroid.x)
stations['y'] = stations['geometry'].apply(lambda geom: geom.centroid.y)
stations = stations[['name_en','lines','x','y']]
stations['name_en'] = stations['name_en'].str.replace(' ', '_')
stations = stations.rename(columns={'name_en': 'stop_name'})

stations_M1 = stations[(stations['lines'] == 'Γραμμή 1-ΜΕΤΡΟ') | (stations['lines'] == 'Γραμμή 1&2-ΜΕΤΡΟ') | (stations['lines'] == 'Γραμμή 1&3-ΜΕΤΡΟ')]
stations_M2 = stations[(stations['lines'] == 'Γραμμή 2-ΜΕΤΡΟ') | (stations['lines'] == 'Γραμμή 2&3-ΜΕΤΡΟ') | (stations['lines'] == 'Γραμμή 1&2-ΜΕΤΡΟ')]
stations_M3 = stations[(stations['lines'] == 'Γραμμή 3-ΜΕΤΡΟ') | (stations['lines'] == 'Γραμμή 2&3-ΜΕΤΡΟ') | (stations['lines'] == 'Γραμμή 1&3-ΜΕΤΡΟ')]
stations_T5 = stations[stations['lines'] == 'Γραμμή 5-ΤΡΑΜ']

stations_M1_A = stations_M1.sort_values(by='y', ascending=True)
stations_M2_A = stations_M2.sort_values(by='y', ascending=True)
stations_M3_A = stations_M3.sort_values(by='x', ascending=True)
stations_T5_A = stations_T5.sort_values(by='y', ascending=True)

stations_M1_R = stations_M1.sort_values(by='y', ascending=False)
stations_M2_R = stations_M2.sort_values(by='y', ascending=False)
stations_M3_R = stations_M3.sort_values(by='x', ascending=False)
stations_T5_R = stations_T5.sort_values(by='y', ascending=False)

row1 = stations_M1_A.iloc[2].copy()
row2 = stations_M1_A.iloc[3].copy()
stations_M1_A.iloc[2] = row2
stations_M1_A.iloc[3] = row1

row1 = stations_M1_R.iloc[7].copy()
row2 = stations_M1_R.iloc[8].copy()
stations_M1_R.iloc[7] = row2
stations_M1_R.iloc[8] = row1

# function to create tram or metro lines (creation of nodes, sections and stops in the road included)
def createMetroTramLine(roads, layer, stations, prefixe, dt, h_start, h_end):
    line = stations.copy()
    line.reset_index(drop=True, inplace=True)

    # creating nodes
    for index, row in line.iterrows():
        roads.register_node(prefixe+'_'+str(index), [row["x"], row["y"]])

    # creating sections
    list_sections = []
    for i in range(len(line) - 1):
        roads.register_section(prefixe+"_"+str(i)+str(i+1), prefixe+"_"+str(i), prefixe+"_"+str(i+1))
        list_sections.append([prefixe+"_"+str(i)+str(i+1)])

    # creating stops
    list_stops = []
    for index, row in line.iterrows():
        if pd.isna(row["stop_name"]):
            name = prefixe + "_" + str(index)+ "_Unknown"
        else:
            name = prefixe + "_" + str(index)+ "_" + row["stop_name"]
        list_stops.append(name)
        if index+1 < len(line):
            roads.register_stop(name, prefixe+'_'+str(index)+str(index+1), 0.)
        else:
            roads.register_stop(name, prefixe + '_' + str(index-1) + str(index), 1.)

    # creating lines
    timetable = TimeTable.create_table_freq(h_start, h_end, dt)
    layer.create_line(prefixe, list_stops, list_sections, timetable)

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

# creating metro layer
metro_service = PublicTransportMobilityService('METRO')
metro_layer = PublicTransportLayer(roads, 'METRO', Metro, METRO_SPEED, services=[metro_service])
createMetroTramLine(roads, metro_layer, stations_M1_A, "M1A", Dt(minutes=METRO_HEADTIME), '05:00:00', '23:59:59')
createMetroTramLine(roads, metro_layer, stations_M2_A, "M2A", Dt(minutes=METRO_HEADTIME), '07:00:00', '23:59:59')
createMetroTramLine(roads, metro_layer, stations_M3_A, "M3A", Dt(minutes=METRO_HEADTIME), '05:00:00', '23:59:59')
createMetroTramLine(roads, metro_layer, stations_M1_R, "M1R", Dt(minutes=METRO_HEADTIME), '05:00:00', '23:59:59')
createMetroTramLine(roads, metro_layer, stations_M2_R, "M2R", Dt(minutes=METRO_HEADTIME), '07:00:00', '23:59:59')
createMetroTramLine(roads, metro_layer, stations_M3_R, "M3R", Dt(minutes=METRO_HEADTIME), '05:00:00', '23:59:59')

# creating tram layer
tram_service = PublicTransportMobilityService("TRAM")
tram_layer = PublicTransportLayer(roads, "TRAM", veh_type=Tram, default_speed=TRAM_SPEED, services=[tram_service])
createMetroTramLine(roads, tram_layer, stations_T5_A, "T5A", Dt(minutes=TRAM_HEADTIME), '05:00:00', '23:59:59')
createMetroTramLine(roads, tram_layer, stations_T5_R, "T5R", Dt(minutes=TRAM_HEADTIME), '05:00:00', '23:59:59')

# creating zone
res = construct_zone_from_sections(roads, "RES", roads.sections)
roads.add_zone(res)

# cconstruction of the graph
odlayer = generate_matching_origin_destination_layer(roads)
mlgraph = MultiLayerGraph([car_layer, metro_layer, tram_layer],odlayer,0.001)

# creating TRANSIT layer to connect the different transports
mlgraph.connect_inter_layers(["METRO", "TRAM"], 100)
mlgraph.connect_intra_layer("METRO", 10)
mlgraph.connect_intra_layer("TRAM", 10)

# save the graph
graph_file = 'inputs/mlgraph_tc_car.json'
save_graph(mlgraph, graph_file)
