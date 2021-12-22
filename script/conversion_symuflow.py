'''
Implement a xml parser of symuflow input to get a MultiModdalGraph
'''

from lxml import etree
from collections import defaultdict
import numpy as np
import matplotlib.pyplot as plt

from mnms.graph import MultiModalGraph
from mnms.tools.io import save_graph
from mnms.mobility_service import BaseMobilityService
from mnms.tools.render import draw_flow_graph, draw_mobility_service
from mnms.log import rootlogger, LOGLEVEL


def convert_symuflow_to_mmgraph(file, speed_car=13.89):
    tree = etree.parse(file)
    root = tree.getroot()

    nodes = defaultdict(list)
    links = dict()

    node_car = set()
    link_car = set()

    tr_elem = root.xpath('/ROOT_SYMUBRUIT/RESEAUX/RESEAU/TRONCONS')[0]
    for tr in tr_elem.iter("TRONCON"):
        lid = tr.attrib['id']

        up_nid = tr.attrib['id_eltamont']
        down_nid = tr.attrib['id_eltaval']
        up_coord = np.fromstring(tr.attrib['extremite_amont'], sep=" ")
        down_coord = np.fromstring(tr.attrib['extremite_aval'], sep=" ")

        nodes[up_nid].append(up_coord)
        nodes[down_nid].append(down_coord)

        if "exclusion_types_vehicules" in tr.attrib:
            if "VL" not in tr.attrib["exclusion_types_vehicules"]:
                link_car.add(lid)
                node_car.add(up_nid)
                node_car.add(down_nid)
        else:
            link_car.add(lid)
            node_car.add(up_nid)
            node_car.add(down_nid)

        if tr.find('POINTS_INTERNES'):
            length = 0
            last_coords = up_coord
            for pi_elem in tr.iter('POINT_INTERNE'):
                curr_coords = np.fromstring(pi_elem.attrib['coordonnees'], sep=' ')
                length += np.linalg.norm(curr_coords-last_coords)
                last_coords = curr_coords
            length += np.linalg.norm(down_coord-last_coords)
            links[lid] = {'UPSTREAM': up_nid, 'DOWNSTREAM': down_nid, 'ID': lid, 'LENGTH': length}
        else:
            links[lid] = {'UPSTREAM': up_nid, 'DOWNSTREAM': down_nid, 'ID': lid, 'LENGTH': None}
        if lid == "T_827029099_FRef_F":
            print('Found it')
            print(links[lid])
    nodes = {n: np.mean(pos, axis=0) for n, pos in nodes.items()}

    arret_elem = root.xpath('/ROOT_SYMUBRUIT/RESEAUX/RESEAU/PARAMETRAGE_VEHICULES_GUIDES/ARRETS')[0]
    link_to_del = set()

    for arret in arret_elem.iter("ARRET"):
        tr_id = arret.attrib['troncon']
        print(tr_id)
        stop_id = arret.attrib['id']
        stop_pos = float(arret.attrib['position'])

        link = links[tr_id]
        upstream = link["UPSTREAM"]
        downstream = link["DOWNSTREAM"]
        pos_up = nodes[upstream]
        pos_down = nodes[downstream]
        dir = pos_down - pos_up
        dir_norm = dir/np.linalg.norm(dir)

        nodes[stop_id] = pos_up + stop_pos*dir_norm

        up_new_lid = f"{upstream}_{stop_id}"
        down_new_lid = f"{stop_id}_{downstream}"
        links[up_new_lid] =  {'UPSTREAM': upstream, 'DOWNSTREAM': stop_id, 'ID': up_new_lid, 'LENGTH': None}
        links[down_new_lid] = {'UPSTREAM': stop_id, 'DOWNSTREAM': downstream, 'ID': down_new_lid, 'LENGTH': None}
        link_to_del.add(tr_id)

        if tr_id in link_car:
            link_car.add(up_new_lid)
            link_car.add(down_new_lid)
            node_car.add(stop_id)

    for lid in link_to_del:
        del links[lid]
        link_car.discard(lid)

    G = MultiModalGraph()
    flow_graph = G.flow_graph

    [flow_graph.add_node(n, pos) for n, pos in nodes.items()]
    num_skip = 0
    for l in links.values():
        try:
            flow_graph.add_link(l['ID'], l['UPSTREAM'], l['DOWNSTREAM'], length=l['LENGTH'])
        except AssertionError:
            rootlogger.warning(f"Skipping troncon: {l['ID']}, nodes {(l['UPSTREAM'], l['DOWNSTREAM'])} already connected")
            num_skip += 1
    rootlogger.warning(f"Number of skipped link: {num_skip}")
    car = BaseMobilityService('CAR', speed_car)

    [car.add_node(n, n) for n in node_car]
    for l in link_car:
        if l in flow_graph._map_lid_nodes:
            upstream = links[l]['UPSTREAM']
            downstream = links[l]['DOWNSTREAM']
            length = flow_graph.links[flow_graph._map_lid_nodes[l]].length
            car.add_link(l, upstream, downstream, {'time': length/speed_car, 'length': length}, reference_links=[l])

    G.add_mobility_service(car)

    G.mobility_graph.check()

    # line_elem = root.xpath("/ROOT_SYMUBRUIT/RESEAUX/RESEAU/PARAMETRAGE_VEHICULES_GUIDES/LIGNES_TRANSPORT_GUIDEES")[0]
    # for line in line_elem.iter('LIGNE_TRANSPORT_GUIDEE'):
    #     lid = line.attrib['id']
    #     service = G.add_mobility_service(lid)
    #     service_nodes = set()
    #     service_links = dict()
    #     service_stops = list()
    #     for link in line.iter("TRONCON"):
    #         unode, dnode = links[link.attrib['id']]
    #         service_nodes.add(unode)
    #         service_nodes.add(dnode)
    #         service_links[link.attrib['id']] = (unode, dnode)
    #
    #     arret_elem = root.xpath("/ROOT_SYMUBRUIT/RESEAUX/RESEAU/PARAMETRAGE_VEHICULES_GUIDES/ARRETS")[0]
    #     for arret in arret_elem.iter('ARRET'):
    #         if arret.attrib['lignes'] == lid:
    #             service_stops.append(arret.attrib['troncon'])
    #
    #     [service.add_node(service_links[s][0], service_links[s][0]) for s in service_stops]
    #     [service._add_link("_".join([lid, service_links[s][0], service_links[s][1]])) for s in service_stops]
    #     [service._add_link("_".join([lid, service_links[s][1], service_links[s][0]])) for s in service_stops]
    #
    # for outer_sid, outer_serv in G._mobility_services.items():
    #     for inner_sid, inner_serv in G._mobility_services.items():
    #         if outer_sid != inner_sid:
    #             for n in outer_serv.nodes.intersection(inner_serv.nodes):
    #                 G.connect_mobility_service(outer_sid, inner_sid, n)
    #
    rootlogger.info("Flow Graph:")
    rootlogger.info(f"Number of nodes: {G.flow_graph.nb_nodes}")
    rootlogger.info(f"Number of links: {G.flow_graph.nb_links}")
    rootlogger.info("Mobility Graph:")
    rootlogger.info(f"Number of nodes: {G.mobility_graph.nb_nodes}")
    rootlogger.info(f"Number of links: {G.mobility_graph.nb_links}")
    fig, ax = plt.subplots()
    draw_flow_graph(ax, G.flow_graph, node_label=False, show_length=True, linkwidth=3)
    plt.show()

    save_graph(G, file.replace('.xml', '.json'), indent=1)


if __name__ == "__main__":
    rootlogger.setLevel(LOGLEVEL.INFO)
    convert_symuflow_to_mmgraph("/Users/florian.gacon/Work/MnMS/script/Lyon_symuviainput_1.xml")