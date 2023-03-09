import os
import sys

try:
    from lxml import etree
except ImportError:
    print("lxml must be installed to use this script, you can install it with 'conda install lxml'")
    sys.exit(-1)

import numpy as np

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

csv_filepath = "KV1_GVB_2609/Csv/POINT.csv"
metro_xml_directory = "KV1_GVB_2609/Xml/METRO"
tram_xml_directory = "KV1_GVB_2609/Xml/TRAM"
bus_xml_directory = "KV1_GVB_2609/Xml/BUS"

def convert_amsterdam_to_mnms():
    ## TRAM

    tram_files = os.listdir(tram_xml_directory)

    roads = RoadDescriptor()

    tram_service = PublicTransportMobilityService('TRAM')
    tram_layer = PublicTransportLayer(roads, "TRAMLayer", Tram, 40, services=[tram_service])

    for tram_file in tram_files:

        parser = etree.XMLParser(remove_comments=True)
        datas = etree.parse(tram_file, parser=parser)
        root = datas.getroot()

        line = root.xpath("/KV1MessageType/LINE")[0]

        line_number = 0
        line_name = ""

        for line_child in line.iterchildren():
            if line_child.tag == "linepublicnumber":
                line_number = line_child.text
            if line_child.tag == "linename":
                line_name = line_child.text

        coord_terminus_1 = [0, 0]
        coord_terminus_2 = [0, 0]

        line_id = "TRAM_" + line_number
        line_length = 0

        generate_pt_line_road(roads, coord_terminus_1, coord_terminus_2, 2, line_id, line_length)

        directions = root.xpath("/KV1MessageType/LINE/JOPAS")[0]

        # for each direction
        lid_1 = line_id + "_1_2"
        lid_2 = line_id + "_2_1"

        # for each stops
        stop_coord_x = 0
        stop_coord_y = 0
        stop_name = "Matterhorn"
        sid = stop_name + "1_2"
        roads.register_stop_abs(sid, lid_1, 0.5, [stop_coord_x, stop_coord_y])



    roads.add_zone(generate_one_zone(roads, "RES"))


    od_layer = generate_matching_origin_destination_layer(roads)
    amsterdam_graph = MultiLayerGraph([tram_layer], od_layer, 1000)

    save_graph(amsterdam_graph, "amsterdam_tc.json")


