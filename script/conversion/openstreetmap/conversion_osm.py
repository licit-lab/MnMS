import argparse
import json
import os
import sys
import base64
import re

from collections import defaultdict
from typing import Dict, List, Optional

import numpy as np
import osmnx as ox

from mnms.graph.road import RoadDescriptor
from mnms.graph.layers import MultiLayerGraph, CarLayer, PublicTransportLayer
from mnms.graph.zone import construct_zone_from_contour
from mnms.generation.layers import get_bounding_box
from mnms.io.graph import save_graph
from mnms.time import TimeTable, Time, Dt
from mnms.vehicles.veh_type import Bus, Metro, Tram
from mnms.log import LOGLEVEL, create_logger

from coordinates import wgs_to_utm

log = create_logger('osm_conversion')

_veh_type_convertor = {'METRO': Metro,
                       'BUS': Bus,
                       'TRAM': Tram}


def convert_osm_to_mnms(osm_query, output_dir, zone_dict: Dict[str, List[str]]=None, car_only=False, mono_res: Optional[str] = None):
    edges = dict()
    nodes = defaultdict(list)
    adjacency = defaultdict(set)
    junctions = dict()

    node_car = set()
    link_car = set()

    roads = RoadDescriptor()

    osm_graph = ox.graph_from_place(osm_query, network_type="drive")

    for iedge, edge in osm_graph.edges.items():
        lid = re.sub(r'\W+', '', str(edge["osmid"]))
        up_nid = iedge[0]
        down_nid = iedge[1]
        length = edge["length"]

        amont_utm = wgs_to_utm(osm_graph.nodes[up_nid]["y"], osm_graph.nodes[up_nid]["x"])
        aval_utm = wgs_to_utm(osm_graph.nodes[down_nid]["y"], osm_graph.nodes[down_nid]["x"])

        coords_amont = np.array(amont_utm)
        coords_aval = np.array(aval_utm)

        nodes[up_nid].append(coords_amont)
        nodes[down_nid].append(coords_aval)

        edges[lid] = {"up": up_nid, "down": down_nid, "length": length}
        adjacency[up_nid].add(down_nid)

        link_car.add(lid)
        node_car.add(up_nid)
        node_car.add(down_nid)

    nodes = {n: np.mean(pos, axis=0) for n, pos in nodes.items()}

    for nid, pos in nodes.items():
        roads.register_node(nid, pos)

    for eid, edata in edges.items():
        roads.register_section(eid, edata['up'], edata['down'], edata['length'])

    if mono_res is None:
        for zid, contour in zone_dict.items():
            roads.add_zone(construct_zone_from_contour(roads, zid, contour))
    else:
        bb = get_bounding_box(roads)
        box = [[bb.xmin, bb.ymin], [bb.xmin, bb.ymax], [bb.xmax, bb.ymax], [bb.xmax, bb.ymin]]
        roads.add_zone(construct_zone_from_contour(roads, mono_res, box))


    car_layer = CarLayer(roads)

    for n in node_car:
        car_layer.create_node(str(n), n)

    for lid in link_car:
        try:
            car_layer.create_link(lid, str(edges[lid]['up']), str(edges[lid]['down']),
                                  {}, road_links=[lid])
        except AssertionError:
            print(f"Skipping troncon: {lid}, nodes already connected")


    mlgraph = MultiLayerGraph([car_layer])

    save_graph(mlgraph, output_dir+'/test.json', indent=1)


def _path_file_type(path):
    if os.path.isfile(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"{path} is not a valid path")


def _path_dir_type(path):
    if os.path.isdir(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"{path} is not a valid path")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Convert OpenStreetMap to MnMS JSON graph')
    parser.add_argument('query', type=str, help='String query, example: "Lyon, France"')
    parser.add_argument('--output_dir', default=os.getcwd(), type=_path_dir_type, help='Path to the output dir')

    command_group = parser.add_mutually_exclusive_group()
    command_group.add_argument('--mono_res', default=None, type=str, help='Use a unique reservoir')
    command_group.add_argument('--multi_res', default=None, type=_path_file_type, help='Path to JSON file containing the mapping section/reservoir')

    args = parser.parse_args()

    log.setLevel(LOGLEVEL.INFO)

    log.info(f"Writing MNMS graph at '{args.output_dir}' ...")
    if args.mono_res is not None:
        convert_osm_to_mnms(args.query, args.output_dir, zone_dict=None, mono_res=args.mono_res)
    elif args.multi_res is not None:
        with open(args.multi_res, 'r') as f:
            res_dict = json.load(f)
        convert_osm_to_mnms(args.query, args.output_dir, res_dict, args.car_only)
    else:
        convert_osm_to_mnms(args.query, args.output_dir)
    log.info(f"Done!")