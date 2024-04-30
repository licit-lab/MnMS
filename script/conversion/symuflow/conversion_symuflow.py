#!/usr/bin/env python

'''
Implement a xml parser of symuflow input to get a MultiModdalGraph
'''
import argparse
import json
import os
import sys

from collections import defaultdict
from typing import Dict, List, Optional

import numpy as np

from mnms.graph.road import RoadDescriptor
from mnms.graph.layers import MultiLayerGraph, CarLayer, PublicTransportLayer
from mnms.graph.zone import construct_zone_from_contour
from mnms.generation.layers import get_bounding_box
from mnms.io.graph import save_graph
from mnms.time import TimeTable, Time, Dt
from mnms.vehicles.veh_type import Bus, Metro, Tram
from mnms.log import LOGLEVEL, create_logger

log = create_logger('symuflow_conversion')

try:
    from lxml import etree
except ImportError:
    log.error("lxml must be installed to use this script, you can install it with 'conda install lxml'")
    sys.exit(-1)

_veh_type_convertor = {'METRO': Metro,
                       'BUS': Bus,
                       'TRAM': Tram}


def convert_symuflow_to_mnms(file, output_dir, zone_dict: Dict[str, List[str]]=None, car_only=False, mono_res: Optional[str] = None):
    parser = etree.XMLParser(remove_comments=True)
    contents = etree.parse(file, parser=parser)
    root = contents.getroot()

    troncons = dict()
    nodes = defaultdict(list)
    adjacency = defaultdict(set)
    junctions = dict()

    node_car = set()
    link_car = set()

    tron = root.xpath("/ROOT_SYMUBRUIT/RESEAUX/RESEAU/TRONCONS")[0]

    roads = RoadDescriptor()



    for tr_elem in tron.iterchildren():
        lid = tr_elem.attrib['id']
        up_nid = tr_elem.attrib["id_eltamont"]
        down_nid = tr_elem.attrib["id_eltaval"]
        coords_amont = np.fromstring(tr_elem.attrib["extremite_amont"], sep=" ")
        coords_aval = np.fromstring(tr_elem.attrib["extremite_aval"], sep=" ")
        nodes[up_nid].append(coords_amont)
        nodes[down_nid].append(coords_aval)

        points = [coords_amont]
        reserved_lane = []
        for tr_child in tr_elem.iterchildren():
            if tr_child.tag == "POINTS_INTERNES":
                for internal_points in tr_child.iterchildren():
                    points.append(
                        np.fromstring(internal_points.attrib["coordonnees"], sep=" ")
                    )
            if tr_child.tag == "VOIES_INTERDITES":
                for lane_elem in tr_child.iterchildren():
                    if lane_elem.attrib["id_typesvehicules"] == "VL":
                        reserved_lane.append(lane_elem.attrib["num_voie"])
        points.append(coords_aval)
        length = np.sum(
            [np.linalg.norm(points[i + 1] - points[i]) for i in range(len(points) - 1)]
        )

        troncons[lid] = {"up": up_nid, "down": down_nid, "length": length}
        adjacency[up_nid].add(down_nid)

        nb_lane = float(tr_elem.attrib.get('nb_voie', '1'))

        if "exclusion_types_vehicules" in tr_elem.attrib:
            if "VL" not in tr_elem.attrib["exclusion_types_vehicules"]:
                link_car.add(lid)
                node_car.add(up_nid)
                node_car.add(down_nid)

        elif tr_elem.find('VOIES_RESERVEES') is not None:
            nb_reserved_lane = sum(1 for _ in tr_elem.iter("VOIE_RESERVEE"))
            if nb_reserved_lane != nb_lane:
                link_car.add(lid)
                node_car.add(up_nid)
                node_car.add(down_nid)
        else:
            link_car.add(lid)
            node_car.add(up_nid)
            node_car.add(down_nid)

    nodes = {n: np.mean(pos, axis=0) for n, pos in nodes.items()}


    for nid, pos in nodes.items():
        roads.register_node(nid, pos)

    for tid, tdata in troncons.items():
        roads.register_section(tid, tdata['up'], tdata['down'], tdata['length'])

    if mono_res is None:
        for zid, contour in zone_dict.items():
            roads.add_zone(construct_zone_from_contour(roads, zid, contour))
    else:
        bb = get_bounding_box(roads)
        box = [[bb.xmin, bb.ymin], [bb.xmin, bb.ymax], [bb.xmax, bb.ymax], [bb.xmax, bb.ymin]]
        roads.add_zone(construct_zone_from_contour(roads, mono_res, box))



    stop_elem = root.xpath('/ROOT_SYMUBRUIT/RESEAUX/RESEAU/PARAMETRAGE_VEHICULES_GUIDES/ARRETS')
    map_tr_stops = dict()
    if stop_elem:
        stop_elem = stop_elem[0]
        for selem in stop_elem.iterchildren():
            tr = selem.attrib['troncon']
            stop_dist = float(selem.attrib['position'])

            link_length = np.linalg.norm(troncons[tr]['length'])

            rel_dist = stop_dist/link_length
            roads.register_stop(selem.attrib['id'], tr, rel_dist)
            map_tr_stops[tr] = {'lines': set(selem.attrib['lignes'].split(' ')),
                                'stop': selem.attrib['id']}

    # mlgraph.roads = roads

    caf = root.xpath("/ROOT_SYMUBRUIT/RESEAUX/RESEAU/CONNEXIONS/CARREFOURSAFEUX")[0]
    rep = root.xpath("/ROOT_SYMUBRUIT/RESEAUX/RESEAU/CONNEXIONS/REPARTITEURS")[0]
    gir = root.xpath("/ROOT_SYMUBRUIT/RESEAUX/RESEAU/CONNEXIONS/GIRATOIRES")[0]

    for elem in [caf, rep, gir]:
        for caf_elem in elem.iterchildren():
            mov = caf_elem.xpath("MOUVEMENTS_AUTORISES")
            junctions[caf_elem.attrib["id"]] = defaultdict(set)
            if mov:
                for auth_elem in mov[0].iterchildren():
                    tr_am = auth_elem.attrib["id_troncon_amont"]
                    if tr_am in troncons:
                        out = auth_elem.xpath("MOUVEMENT_SORTIES")[0]
                        for out_elem in out.iterchildren():
                            tr_av = out_elem.attrib["id_troncon_aval"]
                            if tr_av in troncons:
                                junctions[caf_elem.attrib["id"]][troncons[tr_am]['up']].add(troncons[tr_av]['down'])



    exclude_movements = dict()
    for nid, coords in nodes.items():
        exclude_movements[nid] = defaultdict(set)

        for node_adj in adjacency[nid]:
            if nid in junctions:
                for move_up, move_downs in junctions[nid].items():
                    if node_adj not in move_downs:
                        exclude_movements[nid][move_up].add(node_adj)


    car_layer = CarLayer(roads)
    for n in node_car:
        car_layer.create_node(n, n, exclude_movements.get(n, None))

    for trid in link_car:
        try:
            car_layer.create_link(trid, troncons[trid]['up'], troncons[trid]['down'],
                                  {}, road_links=[trid])
        except AssertionError:
            print(f"Skipping troncon: {trid}, nodes already connected")

    # mlgraph.add_layer(car_layer)

    # -----------------------------------
    # PUBLIC TRANSPORT
    # -----------------------------------

    if not car_only:

        elem_transport_line = root.xpath("/ROOT_SYMUBRUIT/RESEAUX/RESEAU/PARAMETRAGE_VEHICULES_GUIDES/LIGNES_TRANSPORT_GUIDEES")

        if elem_transport_line:
            elem_transport_line = elem_transport_line[0]
            elem_types_veh = root.xpath("/ROOT_SYMUBRUIT/TRAFICS/TRAFIC/TYPES_DE_VEHICULE")[0]
            veh_type_ids = dict()
            veh_speeds = dict()
            for i, telem in enumerate(elem_types_veh.iter('TYPE_DE_VEHICULE')):
                veh_type_ids[i] = telem.attrib['id']
                veh_speeds[telem.attrib['id']] = float(telem.attrib['vx'])
            pt_types = {}

            # Loops on the public transport lines
            for line_elem in elem_transport_line.iter('LIGNE_TRANSPORT_GUIDEE'):
                line_id=line_elem.attrib['id']
                rep_type_elem = line_elem.xpath('REP_TYPEVEHICULES/REP_TYPEVEHICULE')[0]
                coeffs=rep_type_elem.attrib['coeffs']
                ss= [int(x) for x in coeffs.split(" ")]
                pt_type=veh_type_ids[ss.index(1)]

                if pt_type+'Layer' not in pt_types:
                    public_transport = PublicTransportLayer(roads, pt_type + 'Layer', _veh_type_convertor[pt_type],
                                                            veh_speeds[pt_type], services=[])
                    pt_types[pt_type+'Layer'] = public_transport
                else:
                    public_transport = pt_types[pt_type+'Layer']

                # Loads timetable
                cal_elem = line_elem.xpath("CALENDRIER")[0]

                freq_elem = cal_elem.xpath('FREQUENCE')
                if len(freq_elem) > 0:
                    freq_elem = freq_elem[0]
                    start = freq_elem.attrib["heuredepart"]
                    end = freq_elem.attrib["heurefin"]
                    freq = freq_elem.attrib["frequence"]
                    line_timetable = TimeTable.create_table_freq(start, end, Dt(seconds=float(freq)))
                else:
                    line_timetable = TimeTable()
                    for time_elem in cal_elem.iter("HORAIRE"):
                        # print(time_elem.attrib['heuredepart'])
                        line_timetable.table.append(Time(time_elem.attrib['heuredepart']))

                if len(line_timetable.table) == 0:
                    log.warning(f"There is an empty TimeTable for {line_id}, skipping this one")
                else:
                    troncons_elem = line_elem.xpath("TRONCONS")[0]
                    line_tr = [tr_elem.attrib['id'] for tr_elem in troncons_elem.iter('TRONCON')]
                    line_stops = []
                    sections = []

                    sec_buffer = []

                    for i in range(len(line_tr)):
                        tr = line_tr[i]
                        if tr in map_tr_stops and line_id in map_tr_stops[tr]['lines']:
                            sec_buffer.append(tr)
                            line_stops.append(map_tr_stops[tr]['stop'])
                            break

                    for tr in line_tr[i+1:]:
                        sec_buffer.append(tr)
                        if tr in map_tr_stops and line_id in map_tr_stops[tr]['lines']:
                            sections.append(sec_buffer)
                            line_stops.append(map_tr_stops[tr]['stop'])
                            sec_buffer = []
                            sec_buffer.append(tr)

                    public_transport.create_line(line_id, line_stops, sections, line_timetable, bidirectional=False)

                mlgraph = MultiLayerGraph([car_layer]+list(pt_types.values()))

    else:

        mlgraph = MultiLayerGraph([car_layer])

    save_graph(mlgraph, output_dir+'/'+os.path.basename(file).replace('.xml', '.json'), indent=1)


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
    parser = argparse.ArgumentParser(description='Convert Symuflow XML graph to mnms JSON graph')
    parser.add_argument('symuflow_graph', type=_path_file_type, help='Path to the SymuFlow XML file')
    parser.add_argument('--output_dir', default=os.getcwd(), type=_path_dir_type, help='Path to the output dir')
    parser.add_argument('--car_only', action='store_true', help='Convert only the car layer')

    command_group = parser.add_mutually_exclusive_group()
    command_group.add_argument('--mono_res', default=None, type=str, help='Use a unique reservoir')
    command_group.add_argument('--multi_res', default=None, type=_path_file_type, help='Path to JSON file containing the mapping section/reservoir')

    args = parser.parse_args()

    log.setLevel(LOGLEVEL.INFO)

    log.info(f"Writing MNMS graph at '{args.output_dir}' ...")
    if args.mono_res is not None:
        convert_symuflow_to_mnms(args.symuflow_graph, args.output_dir, zone_dict=None, car_only=args.car_only, mono_res=args.mono_res)
    elif args.multi_res is not None:
        with open(args.multi_res, 'r') as f:
            res_dict = json.load(f)
        convert_symuflow_to_mnms(args.symuflow_graph, args.output_dir, res_dict, args.car_only)
    else:
        convert_symuflow_to_mnms(args.symuflow_graph, args.output_dir)
    log.info(f"Done!")
