#!/usr/bin/env python

'''
Implement a xml parser of symuflow input to get a MultiModdalGraph
'''
import argparse
import json
import os
import sys

from collections import defaultdict
from typing import Dict

import numpy as np

from mnms.graph.road import RoadDataBase
from mnms.graph.layers import MultiLayerGraph, CarLayer, PublicTransportLayer
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


# def convert_symuflow_to_mmgraph(file, output_dir, zone_file:str=None):
#
#     tree = etree.parse(file)
#     root = tree.getroot()
#
#     G = MultiModalGraph()
#
#     # Loads the list of vehicle types and their maximum speed
#     elem_types_veh = root.xpath("/ROOT_SYMUBRUIT/TRAFICS/TRAFIC/TYPES_DE_VEHICULE")[0]
#     veh_type_ids = dict()
#     veh_speeds = dict()
#     for i, telem in enumerate(elem_types_veh.iter('TYPE_DE_VEHICULE')):
#         veh_type_ids[i] = telem.attrib['id']
#         veh_speeds[telem.attrib['id']] = float(telem.attrib['vx'])
#
#     # In the case of symuvia input, the first item in the list of the vehicle types is always passenger car (VL)
#     speed_car = veh_speeds['VL']
#
#     #------------
#     # Builds the flow graph consisting of the road network and the public transport network
#     #------------
#
#     nodes = defaultdict(list)
#     sections = dict()
#
#     node_car = set()
#     link_car = set()
#
#     # Loads the nodes and the sections of the road network
#     tr_elem = root.xpath('/ROOT_SYMUBRUIT/RESEAUX/RESEAU/TRONCONS')[0]
#     for tr in tr_elem.iter("TRONCON"):
#         lid = tr.attrib['id']
#
#         up_nid = tr.attrib['id_eltamont']
#         down_nid = tr.attrib['id_eltaval']
#         up_coord = np.fromstring(tr.attrib['extremite_amont'], sep=" ")
#         down_coord = np.fromstring(tr.attrib['extremite_aval'], sep=" ")
#         nb_lane = float(tr.attrib.get('nb_voie', '1'))
#         # vit_reg = tr.attrib['vit_reg']
#         nodes[up_nid].append(up_coord)
#         nodes[down_nid].append(down_coord)
#
#         if "exclusion_types_vehicules" in tr.attrib:
#             if "VL" not in tr.attrib["exclusion_types_vehicules"]:
#                 link_car.add(lid)
#                 node_car.add(up_nid)
#                 node_car.add(down_nid)
#
#         elif tr.find('VOIES_RESERVEES') is not None:
#             # print("RESERVED LANE", lid)
#             nb_reserved_lane = sum(1 for _ in tr.iter("VOIE_RESERVEE"))
#             if nb_reserved_lane != nb_lane:
#                 link_car.add(lid)
#                 node_car.add(up_nid)
#                 node_car.add(down_nid)
#         else:
#             link_car.add(lid)
#             node_car.add(up_nid)
#             node_car.add(down_nid)
#
#         if tr.find('POINTS_INTERNES') is not None:
#             length = 0
#             last_coords = up_coord
#             for pi_elem in tr.iter('POINT_INTERNE'):
#                 curr_coords = np.fromstring(pi_elem.attrib['coordonnees'], sep=' ')
#                 length += np.linalg.norm(curr_coords-last_coords)
#                 last_coords = curr_coords
#             length += np.linalg.norm(down_coord-last_coords)
#             sections[lid] = {'UPSTREAM': up_nid, 'DOWNSTREAM': down_nid, 'ID': lid, 'LENGTH': length, "NB_LANE":nb_lane}
#         else:
#             sections[lid] = {'UPSTREAM': up_nid, 'DOWNSTREAM': down_nid, 'ID': lid, 'LENGTH': None, "NB_LANE":nb_lane}
#
#         if 'vit_reg' in tr.attrib:
#             sections[lid]['VIT_REG'] = float(tr.attrib['vit_reg'])
#
#
#     nodes = {n: np.mean(pos, axis=0) for n, pos in nodes.items()}
#
#     # Loads the nodes (stops) of the public transport network and build the corresponding sections
#     arret_elem = root.xpath('/ROOT_SYMUBRUIT/RESEAUX/RESEAU/PARAMETRAGE_VEHICULES_GUIDES/ARRETS')[0]
#     link_to_del = dict()
#
#     for arret in arret_elem.iter("ARRET"):
#         tr_id = arret.attrib['troncon']
#         stop_id = arret.attrib['id']
#         stop_pos = float(arret.attrib['position'])
#
#         link = sections[tr_id]
#         upstream = link["UPSTREAM"]
#         downstream = link["DOWNSTREAM"]
#         pos_up = nodes[upstream]
#         pos_down = nodes[downstream]
#         dir = pos_down - pos_up
#         dir_norm = dir/np.linalg.norm(dir)
#
#         nodes[stop_id] = pos_up + stop_pos*dir_norm
#
#         up_new_lid = f"{upstream}_{stop_id}"
#         down_new_lid = f"{stop_id}_{downstream}"
#         sections[up_new_lid] =  {'UPSTREAM': upstream, 'DOWNSTREAM': stop_id, 'ID': up_new_lid, 'LENGTH': None, "NB_LANE": 1}
#         sections[down_new_lid] = {'UPSTREAM': stop_id, 'DOWNSTREAM': downstream, 'ID': down_new_lid, 'LENGTH': None, "NB_LANE": 1}
#         link_to_del[tr_id] = (up_new_lid, down_new_lid)
#
#     for lid in link_to_del:
#         del sections[lid]
#         link_car.discard(lid)
#
#     flow_graph = G.flow_graph
#
#     [flow_graph.create_node(n, pos) for n, pos in nodes.items()]
#     num_skip = 0
#     already_present_link = dict()
#     for l in sections.values():
#         try:
#             flow_graph.create_link(l['ID'], l['UPSTREAM'], l['DOWNSTREAM'], length=l['LENGTH'])
#         except AssertionError:
#             log.warning(f"Skipping troncon: {l['ID']}, nodes already connected")
#             already_present_link[l['ID']] = flow_graph.sections[(l['UPSTREAM'], l['DOWNSTREAM'])].id
#             num_skip += 1
#     log.warning(f"Number of skipped link: {num_skip}")
#
#
#     #------------
#     # Builds the layer of the passenger vehicles
#     #------------
#
#     car = CarMobilityGraphLayer('CARLayer', speed_car)
#     car.add_mobility_service(PersonalCarMobilityService())
#
#     [car.create_node(n, n) for n in node_car]
#     for l in link_car:
#         if l in flow_graph._map_lid_nodes:
#             upstream = sections[l]['UPSTREAM']
#             downstream = sections[l]['DOWNSTREAM']
#             length = flow_graph.sections[flow_graph._map_lid_nodes[l]].length
#             car.create_link(l, upstream, downstream, reference_links=[l], costs={'travel_time': length/min(sections[l].get('VIT_REG', speed_car), speed_car), 'length': length} )
#
#     G.add_layer(car)
#
#     #------------
#     # Builds the layers of the public transport (one layer by public transport type)
#     #------------
#
#     pt_types=[]
#     elem_transport_line = root.xpath("/ROOT_SYMUBRUIT/RESEAUX/RESEAU/PARAMETRAGE_VEHICULES_GUIDES/LIGNES_TRANSPORT_GUIDEES")[0]
#
#     # Loops on the public transport lines
#     for line_elem in elem_transport_line.iter('LIGNE_TRANSPORT_GUIDEE'):
#
#         line_id=line_elem.attrib['id']
#         rep_type_elem = line_elem.xpath('REP_TYPEVEHICULES/REP_TYPEVEHICULE')[0]
#         coeffs=rep_type_elem.attrib['coeffs']
#         ss= [int(x) for x in coeffs.split(" ")]
#         pt_type=veh_type_ids[ss.index(1)]
#
#         if pt_type not in pt_types:
#             pt_types.append(pt_type)
#             public_transport = PublicTransportGraphLayer(pt_type+'Layer', _veh_type_convertor[pt_type], veh_speeds[pt_type], services=[PublicTransportMobilityService(pt_type)])
#             G.add_layer(public_transport)
#         else:
#             public_transport = G.layers[pt_type+'Layer']
#
#         # Loads timetable
#         cal_elem = line_elem.xpath("CALENDRIER")[0]
#
#         freq_elem = cal_elem.xpath('FREQUENCE')
#         if len(freq_elem) > 0:
#             freq_elem = freq_elem[0]
#             start = freq_elem.attrib["heuredepart"]
#             end = freq_elem.attrib["heurefin"]
#             freq = freq_elem.attrib["frequence"]
#             line_timetable = TimeTable.create_table_freq(start, end, Dt(seconds=float(freq)))
#         else:
#             line_timetable = TimeTable()
#             for time_elem in cal_elem.iter("HORAIRE"):
#                 # print(time_elem.attrib['heuredepart'])
#                 line_timetable.table.append(Time(time_elem.attrib['heuredepart']))
#
#         if len(line_timetable.table) == 0:
#             log.warning(f"There is an empty TimeTable for {line_id}, skipping this one")
#         else:
#
#             new_line = public_transport.add_line(line_id, line_timetable)
#
#             service_nodes = set()
#             service_links = set()
#             troncons_elem = line_elem.xpath("TRONCONS")[0]
#
#             for tr_elem in troncons_elem.iter('TRONCON'):
#                 tr_id = tr_elem.attrib['id']
#                 # print(tr_id)
#                 if tr_id in link_to_del:
#                     up_lid, down_lid = link_to_del[tr_id]
#                     up_node = sections[up_lid]['UPSTREAM']
#                     down_node = sections[up_lid]['DOWNSTREAM']
#                     service_nodes.add(up_node)
#                     service_nodes.add(down_node)
#                     service_links.add(up_lid)
#
#                     up_node = sections[down_lid]['UPSTREAM']
#                     down_node = sections[down_lid]['DOWNSTREAM']
#                     service_nodes.add(up_node)
#                     service_nodes.add(down_node)
#                     service_links.add(down_lid)
#                 else:
#                     # print('TR IS NOT DELETED')
#                     up_node = sections[tr_id]['UPSTREAM']
#                     down_node = sections[tr_id]['DOWNSTREAM']
#                     service_nodes.add(up_node)
#                     service_nodes.add(down_node)
#                     service_links.add(tr_id)
#                     # print(up_node, down_node)
#             for n in service_nodes:
#                 new_line.add_stop(line_id+'_'+n, n)
#
#             for l in service_links:
#                 if l in already_present_link:
#                     l = already_present_link[l]
#                 up = sections[l]['UPSTREAM']
#                 down = sections[l]['DOWNSTREAM']
#                 length = flow_graph.sections[flow_graph._map_lid_nodes[l]].length
#                 costs = {'travel_time': length/min(sections[l].get('VIT_REG', veh_speeds[pt_type]), veh_speeds[pt_type]),'waiting_time':0.0}
#                 new_line.connect_stops(line_id+'_'+l, line_id+'_'+up, line_id+'_'+down, length, costs=costs, reference_links=[l])
#
#     G.mobility_graph.check()
#     log.info("Flow Graph:")
#     log.info(f"Number of nodes: {G.flow_graph.nb_nodes}")
#     log.info(f"Number of sections: {G.flow_graph.nb_links}")
#     log.info("Mobility Graph:")
#     log.info(f"Number of nodes: {G.mobility_graph.nb_nodes}")
#     log.info(f"Number of sections: {G.mobility_graph.nb_links}")
#     log.info(f"Layers: {list(G.layers.keys())}")
#
#     if zone_file is not None:
#         zone_dict = defaultdict(set)
#         with open(zone_file, 'r') as reader:
#             reader.readline()
#             line = reader.readline()
#             while line:
#                 link, zone = line.split(';')
#                 zone_dict[zone.upper().removesuffix('\n')].add(link)
#
#                 line = reader.readline()
#
#         for zone, sections in sorted(zone_dict.items()):
#             sections = [l for l in sections if l in G.flow_graph._map_lid_nodes]
#             G.add_zone(zone, sections)
#
#     save_graph(G, output_dir+'/'+os.path.basename(file).replace('.xml', '.json'), indent=1)


# def convert_symuflow_to_mmgraph(file, output_dir, zone_file:str=None):
#     parser = etree.XMLParser(remove_comments=True)
#     contents = etree.parse(file, parser=parser)
#     root = contents.getroot()
#
#     troncons = dict()
#     nodes = defaultdict(list)
#     adjacency = defaultdict(set)
#     junctions = dict()
#
#     node_car = set()
#     link_car = set()
#
#     tron = root.xpath("/ROOT_SYMUBRUIT/RESEAUX/RESEAU/TRONCONS")[0]
#
#     for tr_elem in tron.iterchildren():
#         lid = tr_elem.attrib['id']
#         up_nid = tr_elem.attrib["id_eltamont"]
#         down_nid = tr_elem.attrib["id_eltaval"]
#         coords_amont = np.fromstring(tr_elem.attrib["extremite_amont"], sep=" ")
#         coords_aval = np.fromstring(tr_elem.attrib["extremite_aval"], sep=" ")
#         nodes[up_nid].append(coords_amont)
#         nodes[down_nid].append(coords_aval)
#
#         points = [coords_amont]
#         reserved_lane = []
#         for tr_child in tr_elem.iterchildren():
#             if tr_child.tag == "POINTS_INTERNES":
#                 for internal_points in tr_child.iterchildren():
#                     points.append(
#                         np.fromstring(internal_points.attrib["coordonnees"], sep=" ")
#                     )
#             if tr_child.tag == "VOIES_INTERDITES":
#                 for lane_elem in tr_child.iterchildren():
#                     if lane_elem.attrib["id_typesvehicules"] == "VL":
#                         reserved_lane.append(lane_elem.attrib["num_voie"])
#         points.append(coords_aval)
#         length = np.sum(
#             [np.linalg.norm(points[i + 1] - points) for i in range(len(points) - 1)]
#         )
#
#         troncons[lid] = {"up": up_nid, "down": down_nid, "length": length}
#         adjacency[up_nid].add(down_nid)
#
#         nb_lane = float(tr_elem.attrib.get('nb_voie', '1'))
#
#         if "exclusion_types_vehicules" in tr_elem.attrib:
#             if "VL" not in tr_elem.attrib["exclusion_types_vehicules"]:
#                 link_car.add(lid)
#                 node_car.add(up_nid)
#                 node_car.add(down_nid)
#
#         elif tr_elem.find('VOIES_RESERVEES') is not None:
#             nb_reserved_lane = sum(1 for _ in tr_elem.iter("VOIE_RESERVEE"))
#             if nb_reserved_lane != nb_lane:
#                 link_car.add(lid)
#                 node_car.add(up_nid)
#                 node_car.add(down_nid)
#         else:
#             link_car.add(lid)
#             node_car.add(up_nid)
#             node_car.add(down_nid)
#
#     nodes = {n: np.mean(pos, axis=0) for n, pos in nodes.items()}
#
#     caf = root.xpath("/ROOT_SYMUBRUIT/RESEAUX/RESEAU/CONNEXIONS/CARREFOURSAFEUX")[0]
#     rep = root.xpath("/ROOT_SYMUBRUIT/RESEAUX/RESEAU/CONNEXIONS/REPARTITEURS")[0]
#     gir = root.xpath("/ROOT_SYMUBRUIT/RESEAUX/RESEAU/CONNEXIONS/GIRATOIRES")[0]
#
#     for elem in [caf, rep, gir]:
#         for caf_elem in elem.iterchildren():
#             mov = caf_elem.xpath("MOUVEMENTS_AUTORISES")
#             junctions[caf_elem.attrib["id"]] = defaultdict(set)
#             if mov:
#                 for auth_elem in mov[0].iterchildren():
#                     tr_am = auth_elem.attrib["id_troncon_amont"]
#                     if tr_am in troncons:
#                         out = auth_elem.xpath("MOUVEMENT_SORTIES")[0]
#                         for out_elem in out.iterchildren():
#                             tr_av = out_elem.attrib["id_troncon_aval"]
#                             if tr_av in troncons:
#                                 junctions[caf_elem.attrib["id"]][troncons[tr_am]['up']].add(troncons[tr_av]['down'])
#
#     mmgraph = MultiModalGraph()
#     flow = mmgraph.flow_graph
#
#     exclude_movements = dict()
#     for nid, coords in nodes.items():
#         exclude_movements[nid] = defaultdict(set)
#
#         for node_adj in adjacency[nid]:
#             if nid in junctions:
#                 for move_up, move_downs in junctions[nid].items():
#                     if node_adj not in move_downs:
#                         exclude_movements[nid][move_up].add(node_adj)
#
#         flow.create_node(nid, coords)
#
#     for trid, tron in troncons.items():
#         try:
#             flow.create_link(trid, tron['up'], tron['down'], length=tron['length'])
#         except AssertionError:
#             print(f"Skipping troncon: {trid}, nodes already connected")
#
#     car_layer = CarMobilityGraphLayer(services=[PersonalCarMobilityService()])
#     for n in node_car:
#         car_layer.create_node(n, n, exclude_movements.get(n, None))
#
#     for trid in link_car:
#         try:
#             car_layer.create_link(trid, troncons[trid]['up'], troncons[trid]['down'], reference_links=[trid])
#         except AssertionError:
#             print(f"Skipping troncon: {trid}, nodes already connected")
#
#     mmgraph.add_layer(car_layer)
#
#     if zone_file is not None:
#         zone_dict = defaultdict(set)
#         with open(zone_file, 'r') as reader:
#             reader.readline()
#             line = reader.readline()
#             while line:
#                 link, zone = line.split(';')
#                 zone_dict[zone.upper().removesuffix('\n')].add(link)
#
#                 line = reader.readline()
#
#         for zone, links in sorted(zone_dict.items()):
#             links = [l for l in links if l in G.flow_graph._map_lid_nodes]
#             mmgraph.add_zone(zone, links)
#
#     save_graph(mmgraph, output_dir+'/'+os.path.basename(file).replace('.xml', '.json'), indent=1)

def convert_symuflow_to_mnms(file, output_dir, zone_dict: Dict[str, str]=None):
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

    roaddb = RoadDataBase()



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
            [np.linalg.norm(points[i + 1] - points) for i in range(len(points) - 1)]
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
        roaddb.register_node(nid, pos)

    for tid, tdata in troncons.items():
        if zone_dict is None:
            roaddb.register_section(tid, tdata['up'], tdata['down'], tdata['length'])
        else:
            roaddb.register_section(tid, tdata['up'], tdata['down'], tdata['length'], zone_dict[tid])

    stop_elem = root.xpath('/ROOT_SYMUBRUIT/RESEAUX/RESEAU/PARAMETRAGE_VEHICULES_GUIDES/ARRETS')
    map_tr_stops = dict()
    if stop_elem:
        stop_elem = stop_elem[0]
        for selem in stop_elem.iterchildren():
            tr = selem.attrib['troncon']
            stop_dist = float(selem.attrib['position'])

            link_length = np.linalg.norm(troncons[tr]['length'])

            rel_dist = stop_dist/link_length
            roaddb.register_stop(selem.attrib['id'], tr, rel_dist)
            map_tr_stops[tr] = {'lines': set(selem.attrib['lignes'].split(' ')),
                                'stop': selem.attrib['id']}

    # mlgraph.roaddb = roaddb

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


    car_layer = CarLayer(roaddb)
    for n in node_car:
        car_layer.create_node(n, n, exclude_movements.get(n, None))

    for trid in link_car:
        try:
            car_layer.create_link(trid, troncons[trid]['up'], troncons[trid]['down'], {'length': troncons[trid]['length']}, reference_links=[trid])
        except AssertionError:
            print(f"Skipping troncon: {trid}, nodes already connected")

    # mlgraph.add_layer(car_layer)

    # -----------------------------------
    # PUBLIC TRANSPORT
    # -----------------------------------
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
                public_transport = PublicTransportLayer(pt_type+'Layer',
                                                        roaddb,
                                                        _veh_type_convertor[pt_type],
                                                        veh_speeds[pt_type],
                                                        services=[])
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

                for tr in line_tr[i:]:
                    sec_buffer.append(tr)
                    if tr in map_tr_stops and line_id in map_tr_stops[tr]['lines']:
                        sections.append(sec_buffer)
                        line_stops.append(map_tr_stops[tr]['stop'])
                        sec_buffer = []

                public_transport.create_line(line_id, line_stops, sections, line_timetable, bidirectional=False)

        mlgraph = MultiLayerGraph([car_layer]+list(pt_types.values()))

        # for p in pt_types.values():
        #     mlgraph.add_layer(p)

    # if zone_file is not None:
    #     zone_dict = defaultdict(set)
    #     with open(zone_file, 'r') as reader:
    #         reader.readline()
    #         line = reader.readline()
    #         while line:
    #             link, zone = line.split(';')
    #             zone_dict[zone.upper().removesuffix('\n')].add(link)
    #
    #             line = reader.readline()
    #
    #     for zone, links in sorted(zone_dict.items()):
    #         links = [l for l in links if l in G.flow_graph._map_lid_nodes]
    #         mmgraph.add_zone(zone, links)

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

    command_group = parser.add_mutually_exclusive_group()
    command_group.add_argument('--mono_res', default=None, type=str, help='Use a unique reservoir')
    command_group.add_argument('--multi_res', default=None, type=_path_file_type, help='Path to JSON file containing the mapping section/reservoir')

    args = parser.parse_args()

    log.setLevel(LOGLEVEL.INFO)

    log.info(f"Writing MNMS graph at '{args.output_dir}' ...")
    if args.mono_res is not None:
        convert_symuflow_to_mnms(args.symuflow_graph, args.output_dir, zone_dict=defaultdict(lambda: args.mono_res))
    elif args.multi_res is not None:
        with open(args.multi_res, 'r') as f:
            res_dict = json.load(f)
        convert_symuflow_to_mnms(args.symuflow_graph, args.output_dir, res_dict)
    else:
        convert_symuflow_to_mnms(args.symuflow_graph, args.output_dir)
    log.info(f"Done!")
