import os
import math

import pandas as pd
import re
import xml.etree.ElementTree as ET

from coordinates import rd_to_utm
from mnms.graph.layers import PublicTransportLayer, MultiLayerGraph
from mnms.generation.roads import generate_pt_line_road
from mnms.vehicles.veh_type import Tram, Metro, Bus
from mnms.generation.zones import generate_one_zone
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.time import TimeTable, Dt, Time
from mnms.io.graph import load_graph, save_graph

coord_csv_filepath = "KV1_GVB_2609_2/Csv/POINT.csv"
time_csv_filepath = "KV1_GVB_2609_2/Csv/PUJOPASS.csv"
amsterdam_json_filepath = "new_network.json"

metro_xml_directory = "KV1_GVB_2609_2/Xml/METRO"
tram_xml_directory = "KV1_GVB_2609_2/Xml/TRAM"
bus_xml_directory = "KV1_GVB_2609_2/Xml/BUS"

list_tram_lines = []
list_metro_lines = []
list_bus_lines = []

ns = "http://bison.connekt.nl/tmi8/kv1/msg"

## POINTS CSV DATA
df_points = pd.read_csv(coord_csv_filepath, sep='|', converters={"DATAOWNERCODE": str})
df_points = df_points[["DATAOWNERCODE", "LOCATIONXEW", "LOCATIONYNS"]]

## TIMETABLE CSV DATA
# df_time = pd.read_csv(time_csv_filepath, sep='|', converters={"USERSTOPCODE": str})
# df_time = df_time[["USERSTOPCODE", "TARGETARRIVALTIME"]]


def extract_amsterdam_stops():
    ## TRAM ############################################################################################################

    tram_files = os.listdir(tram_xml_directory)
    tram_files_xml = list(filter(lambda f: f.endswith('.xml'), tram_files))

    for tram_file in tram_files_xml:
        xml_tree = ET.parse(tram_xml_directory + "/" + tram_file)

        stop_list = xml_tree.findall(".//{*}USRSTOPbegin")
        line_number = tram_file.replace(".xml", '')

        df_tram_line = pd.DataFrame(columns=["LINE_ID", "STOP_NAME", "STOP_CODE"])

        for stop in stop_list:
            userstopcode = ""
            name = ""

            for child in stop:
                if child.tag == "{" + ns + "}userstopcode":
                    userstopcode = child.text
                if child.tag == "{" + ns + "}name":
                    name = re.sub(r'\W+', '', child.text)

            df_tram_line = df_tram_line.append({'LINE_ID': line_number, 'STOP_NAME': name, 'STOP_CODE': userstopcode},
                                               ignore_index=True)

        df_tram_line = df_tram_line.drop_duplicates(subset=["STOP_NAME"], keep="first")

        list_tram_lines.append(df_tram_line)

    ## METRO ###########################################################################################################

    metro_files = os.listdir(metro_xml_directory)
    metro_files_xml = list(filter(lambda f: f.endswith('.xml'), metro_files))

    for metro_file in metro_files_xml:
        xml_tree = ET.parse(metro_xml_directory + "/" + metro_file)

        stop_list = xml_tree.findall(".//{*}USRSTOPbegin")
        line_number = metro_file.replace(".xml", '')

        df_metro_line = pd.DataFrame(columns=["LINE_ID", "STOP_NAME", "STOP_CODE"])

        for stop in stop_list:
            userstopcode = ""
            name = ""

            for child in stop:
                if child.tag == "{" + ns + "}userstopcode":
                    userstopcode = child.text
                if child.tag == "{" + ns + "}name":
                    name = re.sub(r'\W+', '', child.text)

            df_metro_line = df_metro_line.append(
                {'LINE_ID': line_number, 'STOP_NAME': name, 'STOP_CODE': userstopcode}, ignore_index=True)

        df_metro_line = df_metro_line.drop_duplicates(subset=["STOP_NAME"], keep="first")

        list_metro_lines.append(df_metro_line)

    ## BUS #############################################################################################################

    bus_files = os.listdir(bus_xml_directory)
    bus_files_xml = list(filter(lambda f: f.endswith('.xml'), bus_files))

    for bus_file in bus_files_xml:
        xml_tree = ET.parse(bus_xml_directory + "/" + bus_file)

        stop_list = xml_tree.findall(".//{*}USRSTOPbegin")
        line_number = bus_file.replace(".xml", '')

        df_bus_line = pd.DataFrame(columns=["LINE_ID", "STOP_NAME", "STOP_CODE"])

        for stop in stop_list:
            userstopcode = ""
            name = ""

            for child in stop:
                if child.tag == "{" + ns + "}userstopcode":
                    userstopcode = child.text
                if child.tag == "{" + ns + "}name":
                    name = re.sub(r'\W+', '', child.text)

            df_bus_line = df_bus_line.append(
                {'LINE_ID': line_number, 'STOP_NAME': name, 'STOP_CODE': userstopcode}, ignore_index=True)

        df_bus_line = df_bus_line.drop_duplicates(subset=["STOP_NAME"], keep="first")

        list_bus_lines.append(df_bus_line)

def calculate_line_length(line):
    line_length = 0
    nb_stops = len(line)

    for i in range(nb_stops - 1):
        stop_code = line["STOP_CODE"].iloc[i]
        stop_code_next = line["STOP_CODE"].iloc[i+1]

        stop_coord_x = float(df_points["LOCATIONXEW"].loc[df_points["DATAOWNERCODE"] == stop_code])
        stop_coord_y = float(df_points["LOCATIONYNS"].loc[df_points["DATAOWNERCODE"] == stop_code])
        next_stop_coord_x = float(df_points["LOCATIONXEW"].loc[df_points["DATAOWNERCODE"] == stop_code_next])
        next_stop_coord_y = float(df_points["LOCATIONYNS"].loc[df_points["DATAOWNERCODE"] == stop_code_next])

        stop_coord_x_utm, stop_coord_y_utm = rd_to_utm(stop_coord_x, stop_coord_y)
        next_stop_coord_x_utm, next_top_coord_y_utm = rd_to_utm(next_stop_coord_x, next_stop_coord_y)

        section_length = math.dist([stop_coord_x_utm, stop_coord_y_utm],
                                [next_stop_coord_x_utm, next_top_coord_y_utm])

        line_length = line_length + section_length

    return line_length

def convert_amsterdam_to_mnms():
    
    amsterdam_graph = load_graph(amsterdam_json_filepath)

    ## TRAM

    tram_service = PublicTransportMobilityService('TRAM')
    tram_layer = PublicTransportLayer(amsterdam_graph.roads, "TRAMLayer", Tram, 40, services=[tram_service])

    for tram_line in list_tram_lines:

        line_number = tram_line["LINE_ID"].iloc[0]

        terminus_0_stop_code = tram_line["STOP_CODE"].iloc[0]
        terminus_1_stop_code = tram_line["STOP_CODE"].iloc[-1]

        coord_terminus_0_x = float(df_points["LOCATIONXEW"].loc[df_points["DATAOWNERCODE"] == terminus_0_stop_code])
        coord_terminus_0_y = float(df_points["LOCATIONYNS"].loc[df_points["DATAOWNERCODE"] == terminus_0_stop_code])
        coord_terminus_1_x = float(df_points["LOCATIONXEW"].loc[df_points["DATAOWNERCODE"] == terminus_1_stop_code])
        coord_terminus_1_y = float(df_points["LOCATIONYNS"].loc[df_points["DATAOWNERCODE"] == terminus_1_stop_code])

        coord_terminus_0_x_utm, coord_terminus_0_y_utm = rd_to_utm(coord_terminus_0_x, coord_terminus_0_y)
        coord_terminus_1_x_utm, coord_terminus_1_y_utm = rd_to_utm(coord_terminus_1_x, coord_terminus_1_y)

        line_id = "TRAM_" + str(line_number)

        line_length = calculate_line_length(tram_line)

        generate_pt_line_road(amsterdam_graph.roads, [coord_terminus_0_x_utm, coord_terminus_0_y_utm],
                              [coord_terminus_1_x_utm, coord_terminus_1_y_utm], 2, line_id, line_length)

        # # for each direction
        lid_0 = line_id + "_0_1"
        lid_1 = line_id + "_1_0"
        nb_stops = len(tram_line)

        stops_0 = []
        stops_1 = []

        # # for each stops
        for i in range(nb_stops):
            stop_code = tram_line["STOP_CODE"].iloc[i]
            stop_coord_x = float(df_points["LOCATIONXEW"].loc[df_points["DATAOWNERCODE"] == stop_code])
            stop_coord_y = float(df_points["LOCATIONYNS"].loc[df_points["DATAOWNERCODE"] == stop_code])

            stop_coord_x_utm, stop_coord_y_utm = rd_to_utm(stop_coord_x, stop_coord_y)

            stop_name = tram_line["STOP_NAME"].iloc[i]

            sid_0 = stop_name + "_" + line_number
            sid_1 = stop_name + "_" + line_number + "_2"

            rel_0 = float(i / nb_stops)
            rel_1 = float(1 - (i / nb_stops))

            amsterdam_graph.roads.register_stop_abs(sid_0, lid_0, rel_0, [stop_coord_x_utm, stop_coord_y_utm])
            amsterdam_graph.roads.register_stop_abs(sid_1, lid_1, rel_1, [stop_coord_x_utm, stop_coord_y_utm])

            stops_0.append(sid_0)
            stops_1.append(sid_1)

        stops_1.reverse()

        sections_0 = []
        sections_1 = []

        for i in range(nb_stops - 1):
            sections_0.append([lid_0])
            sections_1.append([lid_1])

        # departures_0 = df_time[df_time["USERSTOPCODE"] == terminus_0_stop_code]
        # departures = departures_0["TARGETARRIVALTIME"].apply(str).values.tolist()
        # departures.sort()

        tram_layer.create_line(lid_0,
                               stops_0,
                               sections_0,
                               TimeTable.create_table_freq('06:00:00', '23:00:00', Dt(minutes=5)))

        tram_layer.create_line(lid_1,
                               stops_1,
                               sections_1,
                               TimeTable.create_table_freq('06:00:00', '23:00:00', Dt(minutes=5)))

    print("TRAM OK")

    ## METRO

    metro_service = PublicTransportMobilityService('METRO')
    metro_layer = PublicTransportLayer(amsterdam_graph.roads, "METROLayer", Metro, 60, services=[metro_service])

    for metro_line in list_metro_lines:

        line_number = metro_line["LINE_ID"].iloc[0]

        terminus_0_stop_code = metro_line["STOP_CODE"].iloc[0]
        terminus_1_stop_code = metro_line["STOP_CODE"].iloc[-1]

        coord_terminus_0_x = float(df_points["LOCATIONXEW"].loc[df_points["DATAOWNERCODE"] == terminus_0_stop_code])
        coord_terminus_0_y = float(df_points["LOCATIONYNS"].loc[df_points["DATAOWNERCODE"] == terminus_0_stop_code])
        coord_terminus_1_x = float(df_points["LOCATIONXEW"].loc[df_points["DATAOWNERCODE"] == terminus_1_stop_code])
        coord_terminus_1_y = float(df_points["LOCATIONYNS"].loc[df_points["DATAOWNERCODE"] == terminus_1_stop_code])

        coord_terminus_0_x_utm, coord_terminus_0_y_utm = rd_to_utm(coord_terminus_0_x, coord_terminus_0_y)
        coord_terminus_1_x_utm, coord_terminus_1_y_utm = rd_to_utm(coord_terminus_1_x, coord_terminus_1_y)

        line_id = "METRO_" + str(line_number)

        line_length = calculate_line_length(metro_line)

        generate_pt_line_road(amsterdam_graph.roads, [coord_terminus_0_x_utm, coord_terminus_0_y_utm],
                              [coord_terminus_1_x_utm, coord_terminus_1_y_utm], 2, line_id, line_length)

        # # for each direction
        lid_0 = line_id + "_0_1"
        lid_1 = line_id + "_1_0"
        nb_stops = len(metro_line)

        stops_0 = []
        stops_1 = []

        # # for each stops
        for i in range(nb_stops):
            stop_code = metro_line["STOP_CODE"].iloc[i]
            stop_coord_x = float(df_points["LOCATIONXEW"].loc[df_points["DATAOWNERCODE"] == stop_code])
            stop_coord_y = float(df_points["LOCATIONYNS"].loc[df_points["DATAOWNERCODE"] == stop_code])

            stop_coord_x_utm, stop_coord_y_utm = rd_to_utm(stop_coord_x, stop_coord_y)

            stop_name = metro_line["STOP_NAME"].iloc[i]

            sid_0 = stop_name + "_" + line_number
            sid_1 = stop_name + "_" + line_number + "_2"

            rel_0 = float(i / nb_stops)
            rel_1 = float(1 - (i / nb_stops))

            amsterdam_graph.roads.register_stop_abs(sid_0, lid_0, rel_0, [stop_coord_x_utm, stop_coord_y_utm])
            amsterdam_graph.roads.register_stop_abs(sid_1, lid_1, rel_1, [stop_coord_x_utm, stop_coord_y_utm])

            stops_0.append(sid_0)
            stops_1.append(sid_1)

        stops_1.reverse()

        sections_0 = []
        sections_1 = []

        for i in range(nb_stops - 1):
            sections_0.append([lid_0])
            sections_1.append([lid_1])

        # departures_0 = df_time[df_time["USERSTOPCODE"] == terminus_0_stop_code]
        # departures = departures_0["TARGETARRIVALTIME"].values.tolist()
        # departures.sort()

        metro_layer.create_line(lid_0,
                               stops_0,
                               sections_0,
                               TimeTable.create_table_freq('05:00:00', '23:59:59', Dt(minutes=3)))

        metro_layer.create_line(lid_1,
                               stops_1,
                               sections_1,
                               TimeTable.create_table_freq('05:00:00', '23:59:59', Dt(minutes=3)))

    print("METRO OK")

    ## BUS

    bus_service = PublicTransportMobilityService('BUS')
    bus_layer = PublicTransportLayer(amsterdam_graph.roads, "BUSLayer", Bus, 20, services=[bus_service])

    for bus_line in list_bus_lines:

        line_number = bus_line["LINE_ID"].iloc[0]

        terminus_0_stop_code = bus_line["STOP_CODE"].iloc[0]
        terminus_1_stop_code = bus_line["STOP_CODE"].iloc[-1]

        coord_terminus_0_x = float(df_points["LOCATIONXEW"].loc[df_points["DATAOWNERCODE"] == terminus_0_stop_code])
        coord_terminus_0_y = float(df_points["LOCATIONYNS"].loc[df_points["DATAOWNERCODE"] == terminus_0_stop_code])
        coord_terminus_1_x = float(df_points["LOCATIONXEW"].loc[df_points["DATAOWNERCODE"] == terminus_1_stop_code])
        coord_terminus_1_y = float(df_points["LOCATIONYNS"].loc[df_points["DATAOWNERCODE"] == terminus_1_stop_code])

        coord_terminus_0_x_utm, coord_terminus_0_y_utm = rd_to_utm(coord_terminus_0_x, coord_terminus_0_y)
        coord_terminus_1_x_utm, coord_terminus_1_y_utm = rd_to_utm(coord_terminus_1_x, coord_terminus_1_y)

        line_id = "BUS_" + str(line_number)

        line_length = calculate_line_length(bus_line)

        generate_pt_line_road(amsterdam_graph.roads, [coord_terminus_0_x_utm, coord_terminus_0_y_utm],
                              [coord_terminus_1_x_utm, coord_terminus_1_y_utm], 2, line_id, line_length)

        # # for each direction
        lid_0 = line_id + "_0_1"
        lid_1 = line_id + "_1_0"
        nb_stops = len(bus_line)

        stops_0 = []
        stops_1 = []

        # # for each stops
        for i in range(nb_stops):
            stop_code = bus_line["STOP_CODE"].iloc[i]
            stop_coord_x = float(df_points["LOCATIONXEW"].loc[df_points["DATAOWNERCODE"] == stop_code])
            stop_coord_y = float(df_points["LOCATIONYNS"].loc[df_points["DATAOWNERCODE"] == stop_code])

            stop_coord_x_utm, stop_coord_y_utm = rd_to_utm(stop_coord_x, stop_coord_y)

            stop_name = bus_line["STOP_NAME"].iloc[i]

            sid_0 = stop_name + "_" + line_number
            sid_1 = stop_name + "_" + line_number + "_2"

            rel_0 = float(i / nb_stops)
            rel_1 = float(1 - (i / nb_stops))

            amsterdam_graph.roads.register_stop_abs(sid_0, lid_0, rel_0, [stop_coord_x_utm, stop_coord_y_utm])
            amsterdam_graph.roads.register_stop_abs(sid_1, lid_1, rel_1, [stop_coord_x_utm, stop_coord_y_utm])

            stops_0.append(sid_0)
            stops_1.append(sid_1)

        stops_1.reverse()

        sections_0 = []
        sections_1 = []

        for i in range(nb_stops - 1):
            sections_0.append([lid_0])
            sections_1.append([lid_1])

        # departures_0 = df_time[df_time["USERSTOPCODE"] == terminus_0_stop_code]
        # departures = departures_0["TARGETARRIVALTIME"].values.tolist()
        # departures.sort()

        bus_layer.create_line(lid_0,
                                stops_0,
                                sections_0,
                                TimeTable.create_table_freq('06:00:00', '22:00:00', Dt(minutes=10)))

        bus_layer.create_line(lid_1,
                                stops_1,
                                sections_1,
                                TimeTable.create_table_freq('06:00:00', '22:00:00', Dt(minutes=10)))

    print("BUS OK")

    amsterdam_graph.roads.add_zone(generate_one_zone("RES", amsterdam_graph.roads))

    new_amsterdam_graph = MultiLayerGraph([bus_layer, tram_layer, metro_layer], None, None)

    save_graph(new_amsterdam_graph, "amsterdam_tc.json")


extract_amsterdam_stops()
convert_amsterdam_to_mnms()
