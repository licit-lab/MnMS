### WORK IN PROGRESS ###
# NOTE: All lines are considered as buses

###############
### Imports ###
###############

import os
import numpy as np
import pandas as pd

from gtfs_functions import Feed

from coordinates import wgs_to_utm
from mnms.graph.layers import PublicTransportLayer, MultiLayerGraph
from mnms.generation.roads import generate_pt_line_road, generate_one_zone
from mnms.vehicles.veh_type import Tram, Metro, Bus
from mnms.generation.zones import generate_one_zone
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.time import TimeTable, Dt, Time
from mnms.io.graph import load_graph, save_graph


##################
### Parameters ###
##################

gtfs_path = "gtfs-nl.zip" # gtfs zip folder
mnms_json_filepath = ".json" # mlgraph with the road network only

mlgraph_dump_file = ".json"

# Default speeds
traditional_vehs_default_speed = 13.8 # m/s
metro_default_speed = 15 # m/s
tram_default_speed = 18 # m/s

# PT operation parameters
bus_freq = Dt(minutes=8)
metro_freq = Dt(minutes=4)
tram_freq = Dt(minutes=10)
operation_start_time = '05:00:00'
operation_end_time = '23:00:00'


#################
### Functions ###
#################

_norm = np.linalg.norm

def extract_gtfs_stops(feed):

    routes = feed.routes
    stops = feed.stops
    stop_times = feed.stop_times
    trips = feed.trips
    shapes = feed.shapes

    # Init the list of lines
    list_lines = []

    for route in routes:
        line_stops = []

        route_id = route["route_id"]

        filtered_trips = trips.loc[trips['route_id'] == route_id]

        # Performing the equivalent of INNER JOINs
        merged_data = filtered_trips.merge(stop_times, on='trip_id').merge(stops, on='stop_id')

        # Selecting distinct stop_id and stop_name
        distinct_stops = merged_data[['route_id', 'stop_id', 'stop_name_y', 'stop_lat_y', 'stop_lon_y', 'geometry_y']].drop_duplicates(
            subset="stop_name_y", keep="first")

        # Seperate the two directions of this line
        # NB: this part of the code supposes that the second stop in one direction and the penultimate stop in the other direction are the same !
        for i in range(1, len(distinct_stops) - 1):
            if distinct_stops.iloc[i - 1]['stop_name_y'] == distinct_stops.iloc[i + 1]['stop_name_y']:
                df_line_dir1 = distinct_stops.iloc[:i + 1]
                df_line_dir1 = df_line_dir1.assign(LINE_ID=df_line_dir1.iloc[0]['route_id'] + '_DIR1')
                df_line_dir1.reset_index(drop=True, inplace=True)
                df_line_dir2 = distinct_stops.iloc[i:]
                df_line_dir2 = df_line_dir2.assign(LINE_ID=df_line_dir2.iloc[0]['route_id'] + '_DIR2')
                df_line_dir2.reset_index(drop=True, inplace=True)


    # Append two lines, one per direction
    list_lines.append(df_line_dir1)
    list_lines.append(df_line_dir2)

    return list_lines


def generate_public_transportation_lines(layer, list_lines, freq, operation_start_time, operation_end_time, prefix_line_name):
    """Function that generates public transportation lines on a layer with a certain frequency.

    Args:
    - layer: the layer on which the lines should be created
    - list_lines: list the lines to create, one line is represented by a dataframe with LINE_ID, STOP_NAME, and STOP_CODE as columns
    - freq: frequency to apply on the lines created, shoud be a Dt type object
    - operation_start_time: time at which the timetables should start, str
    - operation_end_time: time at which the timetables should end, str
    - prefix_line_name: str corresponding to the prefix to add to the line id to name the line

    Returns:
    None
    """
    for line in list_lines:
        line_id = line.iloc[0]['LINE_ID']
        line_name = prefix_line_name + line_id
        stops = [line_name + f'_{ind}' for ind in line.index]
        sections = [[line_name + f'_{ind}_{ind+1}', line_name + f'_{ind+1}_{ind+2}'] for ind in list(line.index)[:-2]] + [[line_name + f'_{line.index[-2]}_{line.index[-1]}']]
        layer.create_line(line_name, stops, sections, TimeTable.create_table_freq(operation_start_time, operation_end_time, freq))


#################
### Script ###
#################

feed = Feed(gtfs_path)

lines = extract_gtfs_stops(feed)

### Get the MLGraph without TCs
mnms_graph = load_graph(mnms_json_filepath)
roads = mnms_graph.roads

### Add the nodes, sections, and stops related to each PT line to the roadDescriptor
pt_lines = lines
pt_lines_types = ['BUS'] * len(lines)
pt_nodes = {}
for line, line_type in zip(pt_lines, pt_lines_types):
    for ind, stop in line.iterrows():
        lat = float(stop["stop_lat_y"]) # TODO: Convert to MnMS coordinates
        lon = float(stop["stop_lon_y"]) # TODO: Convert to MnMS coordinates
        x_utm, y_utm = wgs_to_utm(lat, lon)
        node_id = line_type + '_' + stop['route_id'] + '_' + str(ind)
        pt_nodes[node_id] = [x_utm,y_utm]
        roads.register_node(node_id, [x_utm, y_utm])
        if ind > 0:
            onode_id = line_type + '_' + stop['route_id'] + '_' + str(ind-1)
            dnode_id = node_id
            section_id = line_type + '_' + stop['route_id'] + '_' + str(ind-1) + '_' + str(ind)
            section_length = _norm(np.array(pt_nodes[onode_id]) - np.array(pt_nodes[dnode_id]))
            roads.register_section(section_id, onode_id, dnode_id, section_length)
            roads.register_stop(onode_id, section_id, 0.)
        if ind == max(line.index):
            roads.register_stop(dnode_id, section_id, 1.)

### Overwrite the roads zoning with a new zoning including all sections
roads.add_zone(generate_one_zone("RES", roads))

### Create the PT layers, mob services and lines
# Bus
bus_service = PublicTransportMobilityService('BUS')
bus_layer = PublicTransportLayer(roads, 'BUSLayer', Bus, traditional_vehs_default_speed,
        services=[bus_service])
generate_public_transportation_lines(bus_layer, lines, bus_freq, operation_start_time, operation_end_time, 'BUS_')