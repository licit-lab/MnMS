import os

import numpy as np
import pandas as pd

from coordinates import rd_to_wgs, wgs_to_utm
from mnms.graph.road import RoadDescriptor
from mnms.graph.layers import PublicTransportLayer, MultiLayerGraph
from mnms.generation.layers import generate_matching_origin_destination_layer
from mnms.generation.roads import generate_pt_line_road
from mnms.vehicles.veh_type import Tram
from mnms.generation.zones import generate_one_zone
from mnms.mobility_service.public_transport import PublicTransportMobilityService
from mnms.time import TimeTable, Dt, Time
from mnms.io.graph import save_graph

csv_filepath = "KV1_GVB_2609_2/Csv/POINT.csv"
metro_xml_directory = "KV1_GVB_2609_2/Xml/METRO"
tram_xml_directory = "KV1_GVB_2609_2/Xml/TRAM"
bus_xml_directory = "KV1_GVB_2609_2/Xml/BUS"

def convert_amsterdam_to_mnms():
    ## POINTS CSV DATA

    df_points = pd.read_csv(csv_filepath, sep='|', converters={"DATAOWNERCODE": str})
    df_points = df_points[["DATAOWNERCODE", "LOCATIONXEW", "LOCATIONYNS"]]

    ## TRAM

    tram_files = os.listdir(tram_xml_directory)
    tram_files_csv = list(filter(lambda f: f.endswith('.csv'), tram_files))

    roads = RoadDescriptor()

    tram_service = PublicTransportMobilityService('TRAM')
    tram_layer = PublicTransportLayer(roads, "TRAMLayer", Tram, 40, services=[tram_service])

    for tram_file in tram_files_csv:

        df_stops = pd.read_csv(tram_xml_directory+'/'+tram_file, sep=';', converters={"STOP_CODE": str})
        print(df_stops)

        line_number = df_stops["LINE_ID"].iloc[0]

        terminus_0_stop_code = df_stops["STOP_CODE"].iloc[0]
        terminus_1_stop_code = df_stops["STOP_CODE"].iloc[-1]

        coord_terminus_0 = [float(df_points["LOCATIONXEW"].loc[df_points["DATAOWNERCODE"] == terminus_0_stop_code]), float(df_points["LOCATIONYNS"].loc[df_points["DATAOWNERCODE"] == terminus_0_stop_code])]
        coord_terminus_1 = [float(df_points["LOCATIONXEW"].loc[df_points["DATAOWNERCODE"] == terminus_1_stop_code]), float(df_points["LOCATIONYNS"].loc[df_points["DATAOWNERCODE"] == terminus_1_stop_code])]

        line_id = "TRAM_" + str(line_number)
        line_length = 0

        generate_pt_line_road(roads, coord_terminus_0, coord_terminus_1, 2, line_id, line_length)

        # # for each direction
        lid_0 = line_id + "_0_1"
        lid_1 = line_id + "_1_0"
        nb_stops = len(df_stops)

        #
        # # for each stops
        for i in range(nb_stops):
            stop_code = df_stops.loc[i, "STOP_CODE"]
            stop_coord_x = float(df_points["LOCATIONXEW"].loc[df_points["DATAOWNERCODE"] == stop_code])
            stop_coord_y = float(df_points["LOCATIONYNS"].loc[df_points["DATAOWNERCODE"] == stop_code])
            stop_name = df_stops.loc[i, "STOP_NAME"]

            sid_0 = stop_name
            sid_1 = stop_name + "2"

            rel_0 = float(i / nb_stops)
            rel_1 = float(1 - (i / nb_stops))

            roads.register_stop_abs(sid_0, lid_0, rel_0, [stop_coord_x, stop_coord_y])
            roads.register_stop_abs(sid_1, lid_1, rel_1, [stop_coord_x, stop_coord_y])



    roads.add_zone(generate_one_zone("RES", roads))

    od_layer = generate_matching_origin_destination_layer(roads)
    amsterdam_graph = MultiLayerGraph([tram_layer], od_layer, 1000)

    save_graph(amsterdam_graph, "amsterdam_tc.json")


convert_amsterdam_to_mnms()