###############
### Imports ###
###############
import os
import math
import sys
import numpy as np
import matplotlib.pyplot as plt

import pandas as pd
import re
import xml.etree.ElementTree as ET

from coordinates import rd_to_utm
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

# Files and directories
coord_csv_filepath = "KV1_GVB_2609_2/Csv/POINT.csv" # file with coordinates of the network
amsterdam_json_filepath = "new_network.json" # mlgraph with the road network only

metro_xml_directory = "KV1_GVB_2609_2/Xml/METRO" # Definition of operation patterns for METRO lines
tram_xml_directory = "KV1_GVB_2609_2/Xml/TRAM" # Definition of operation patterns for TRAM lines
bus_xml_directory = "KV1_GVB_2609_2/Xml/BUS" # Definition of operation patterns for BUS lines
ns = "http://bison.connekt.nl/tmi8/kv1/msg" # something related to xml domain

mlgraph_dump_file = 'amsterdam_tc_improved.json'

# Points coordinates
df_points = pd.read_csv(coord_csv_filepath, sep='|', converters={"DATAOWNERCODE": str})
df_points = df_points[["DATAOWNERCODE", "LOCATIONXEW", "LOCATIONYNS"]]

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

def extract_amsterdam_stops(xml_dir):
    """Function that create the list of lines for one public transportation type.
    WARNING: this function is made simple, it cannot deal with different operation patterns for one line, and could
    not deal with BUS 232 and BUS 233 which have specific operation patterns. We removed these two lines from the data
    for now.

    Args:
    - xml_dir: directory where the xml files for each line of a public transportation types are located

    Returns:
    - list_lines: list of lines, a line is represented by a dataframe with LINE_ID, STOP_NAME, and STOP_CODE as columns
    """
    # Get all files in xml_dir, there should be one file per public transportation line
    files = os.listdir(xml_dir)
    files_xml = list(filter(lambda f: f.endswith('.xml'), files))

    # Init the list of lines
    list_lines = []

    # Build each line
    for file in files_xml:
        xml_tree = ET.parse(xml_dir + "/" + file)

        stop_list = xml_tree.findall(".//{*}USRSTOPbegin")
        last_stop = xml_tree.findall(".//{*}USRSTOPend")[-1]
        stop_list.append(last_stop)

        line_number = file.replace(".xml", '') # the line number is the file name

        line_stops = []

        # Get the stop list for this line
        # NB: this part of the code supposes that we have only one operation pattern defined in the file
        for stop in stop_list:
            userstopcode = ""
            name = ""

            for child in stop:
                if child.tag == "{" + ns + "}userstopcode":
                    userstopcode = child.text
                if child.tag == "{" + ns + "}name":
                    name = re.sub(r'\W+', '', child.text)
            line_stops.append({'LINE_ID': line_number, 'STOP_NAME': name, 'STOP_CODE': userstopcode})

        df_line = pd.DataFrame(line_stops, columns=["LINE_ID", "STOP_NAME", "STOP_CODE"])

        # Seperate the two directions of this line
        # NB: this part of the code supposes that the second stop in one direction and the penultimate stop in the other direction are the same !
        for i in range(1,len(df_line)-1):
            if df_line.iloc[i-1]['STOP_NAME'] == df_line.iloc[i+1]['STOP_NAME']:
                df_line_dir1 = df_line.iloc[:i+1]
                df_line_dir1 = df_line_dir1.assign(LINE_ID=df_line_dir1.iloc[0]['LINE_ID'] + '_DIR1')
                df_line_dir1.reset_index(drop=True, inplace=True)
                df_line_dir2 = df_line.iloc[i:]
                df_line_dir2 = df_line_dir2.assign(LINE_ID=df_line_dir2.iloc[0]['LINE_ID'] + '_DIR2')
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


##############
### Script ###
##############

### Get the lines definition from the data
lines = []
list_bus_lines = extract_amsterdam_stops(bus_xml_directory)
list_tram_lines = extract_amsterdam_stops(tram_xml_directory)
list_metro_lines = extract_amsterdam_stops(metro_xml_directory) # /!\ keep only one JOPA for each direction in the data file
                                                                    # JOPA correspond to different operation patterns, eg express train that do not stop at certain stations
### Get the MLGraph without TCs
amsterdam_graph = load_graph(amsterdam_json_filepath)
roads = amsterdam_graph.roads

### Add the nodes, sections, and stops related to each PT line to the roadDescriptor
pt_lines = list_tram_lines + list_metro_lines + list_bus_lines
pt_lines_types = ['TRAM'] * len(list_tram_lines) + ['METRO'] * len(list_metro_lines) + ['BUS'] * len(list_bus_lines)
pt_nodes = {}
for line, line_type in zip(pt_lines, pt_lines_types):
    for ind, stop in line.iterrows():
        x = float(df_points["LOCATIONXEW"].loc[df_points["DATAOWNERCODE"] == stop['STOP_CODE']])
        y = float(df_points["LOCATIONYNS"].loc[df_points["DATAOWNERCODE"] == stop['STOP_CODE']])
        x_utm, y_utm = rd_to_utm(x, y)
        node_id = line_type + '_' + stop['LINE_ID'] + '_' + str(ind)
        pt_nodes[node_id] = [x_utm,y_utm]
        roads.register_node(node_id, [x_utm, y_utm])
        if ind > 0:
            onode_id = line_type + '_' + stop['LINE_ID'] + '_' + str(ind-1)
            dnode_id = node_id
            section_id = line_type + '_' + stop['LINE_ID'] + '_' + str(ind-1) + '_' + str(ind)
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
generate_public_transportation_lines(bus_layer, list_bus_lines, bus_freq, operation_start_time, operation_end_time, 'BUS_')
# Metro
metro_service = PublicTransportMobilityService('METRO')
metro_layer = PublicTransportLayer(roads, 'METROLayer', Metro, metro_default_speed,
        services=[metro_service])
generate_public_transportation_lines(metro_layer, list_metro_lines, metro_freq,operation_start_time, operation_end_time, 'METRO_')
# Tram
tram_service = PublicTransportMobilityService('TRAM')
tram_layer = PublicTransportLayer(roads, 'TRAMLayer', Tram, tram_default_speed,
        services=[tram_service])
generate_public_transportation_lines(tram_layer, list_tram_lines, tram_freq, operation_start_time, operation_end_time, 'TRAM_')

### Create the MLGraph with PT
mlgraph = MultiLayerGraph([bus_layer, tram_layer, metro_layer], None, None)

### Save the graph
save_graph(mlgraph, mlgraph_dump_file)
