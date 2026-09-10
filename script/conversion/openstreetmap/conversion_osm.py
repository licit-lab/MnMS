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


# Create logger for script output
log = create_logger('osm_conversion')

# Mapping from vehicle type name to class
_veh_type_convertor = {'METRO': Metro,
                       'BUS': Bus,
                       'TRAM': Tram}


# This script needs osmnx to run, if not installed please run command: pip install osmnx


# Main function to convert an OSM place query to an MnMS-compatible JSON graph
def convert_osm_to_mnms(osm_query, output_file, zone_dict: Dict[str, List[str]] = None, car_only=False, mono_res: Optional[str] = None):
    edges = dict()
    nodes = defaultdict(list)

    node_car = set()
    link_car = set()

    # Road descriptor to register nodes and sections
    roads = RoadDescriptor()

    # Load road network from OpenStreetMap using a place name query
    osm_graph = ox.graph_from_place(osm_query, network_type="drive")

    # Process edges from the OSM graph
    for iedge, edge in osm_graph.edges.items():
        lid = re.sub(r'\W+', '', str(edge["osmid"]))  # Sanitize edge ID
        up_nid = iedge[0]
        down_nid = iedge[1]
        length = edge["length"]

        # Get WGS coordinates for upstream and downstream nodes
        up_node = osm_graph.nodes[up_nid]
        down_node = osm_graph.nodes[down_nid]

        # Convert to UTM coordinates
        amont_utm = wgs_to_utm(up_node["y"], up_node["x"])
        aval_utm = wgs_to_utm(down_node["y"], down_node["x"])

        coords_amont = np.array(amont_utm)
        coords_aval = np.array(aval_utm)

        # Store coordinates for averaging later
        nodes[up_nid].append(coords_amont)
        nodes[down_nid].append(coords_aval)

        # Store edge information
        edges[lid] = {"up": up_nid, "down": down_nid, "length": length}

        # Track which nodes and links are part of the car layer
        link_car.add(lid)
        node_car.add(up_nid)
        node_car.add(down_nid)

    # Average node positions if multiple coordinates were found
    nodes = {n: np.mean(pos, axis=0) for n, pos in nodes.items()}

    # Register nodes in the road descriptor
    for nid, pos in nodes.items():
        roads.register_node(nid, pos)

    # Register sections (edges) in the road descriptor
    for eid, edata in edges.items():
        roads.register_section(eid, edata['up'], edata['down'], edata['length'])

    # Define zones: either multiple zones from file or a bounding box for a single zone
    if mono_res is None:
        for zid, contour in zone_dict.items():
            roads.add_zone(construct_zone_from_contour(roads, zid, contour))
    else:
        bb = get_bounding_box(roads)
        box = [[bb.xmin, bb.ymin], [bb.xmin, bb.ymax], [bb.xmax, bb.ymax], [bb.xmax, bb.ymin]]
        roads.add_zone(construct_zone_from_contour(roads, mono_res, box))

    # Create car layer
    car_layer = CarLayer(roads)

    # Create car layer nodes
    for n in node_car:
        car_layer.create_node(str(n), n)

    # Create car layer links
    for lid in link_car:
        try:
            car_layer.create_link(lid, str(edges[lid]['up']), str(edges[lid]['down']),
                                  {}, road_links=[lid])
        except AssertionError:
            print(f"Skipping troncon: {lid}, nodes already connected")

    # Wrap everything in a multilayer graph
    mlgraph = MultiLayerGraph([car_layer])

    # Save the graph to file
    save_graph(mlgraph, output_file, indent=1)


# Helper to check if the path is a valid file
def _path_file_type(path):
    if os.path.isfile(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"{path} is not a valid path")


# Helper to check if the path is a valid directory
def _path_dir_type(path):
    if os.path.isdir(path):
        return path
    else:
        raise argparse.ArgumentTypeError(f"{path} is not a valid path")


# Helper function for output path (no need to exist)
def _output_file_type(path):
    """
    Validates only the directory part of the path exists,
    but allows the file itself to not exist yet.
    """
    directory = os.path.dirname(path) or "."
    if os.path.isdir(directory):
        return path
    else:
        raise argparse.ArgumentTypeError(f"Directory {directory} does not exist")


# Entry point of the script
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Convert OpenStreetMap to MnMS JSON graph')
    parser.add_argument('query', type=str, help='String query, example: "Lyon, France"')
    parser.add_argument("osm_output_file", type=_output_file_type, help="Path to the OpenStreetMap JSON output file (directory must exists)")

    # Define mutually exclusive zone definitions (single vs. multiple reservoirs)
    command_group = parser.add_mutually_exclusive_group()
    command_group.add_argument('--mono_res', default=None, type=str, help='Use a unique reservoir')
    command_group.add_argument('--multi_res', default=None, type=_path_file_type, help='Path to JSON file containing the mapping section/reservoir')

    args = parser.parse_args()

    # Set log level
    log.setLevel(LOGLEVEL.INFO)

    log.info(f"Writing MNMS graph at '{args.output_dir}' ...")

    # Run conversion with appropriate zone definition
    if args.mono_res is not None:
        convert_osm_to_mnms(args.query, args.osm_output_file, zone_dict=None, mono_res=args.mono_res)
    elif args.multi_res is not None:
        with open(args.multi_res, 'r') as f:
            res_dict = json.load(f)
        convert_osm_to_mnms(args.query, args.osm_output_file, res_dict, args.car_only)
    else:
        convert_osm_to_mnms(args.query, args.osm_output_file)

    log.info(f"Done!")
