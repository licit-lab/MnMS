'''
Implement a xml parser of symuflow input to get a MultiModdalGraph
'''

from lxml import etree
from collections import defaultdict
import numpy as np
import matplotlib.pyplot as plt

from mnms.graph import MultiModalGraph
from mnms.tools.io import save_graph
from mnms.tools.render import draw_flow_graph, draw_mobility_service
from mnms.log import rootlogger, LOGLEVEL


def convert_symuflow_to_mmgraph(file):
    tree = etree.parse(file)
    root = tree.getroot()

    nodes = defaultdict(list)
    links = dict()

    tr_elem = root.xpath('/ROOT_SYMUBRUIT/RESEAUX/RESEAU/TRONCONS')[0]
    for tr in tr_elem.iter("TRONCON"):
        lid = tr.attrib['id']
        up_nid = tr.attrib['id_eltamont']
        down_nid = tr.attrib['id_eltaval']
        up_coord = np.fromstring(tr.attrib['extremite_amont'], sep=" ")
        down_coord = np.fromstring(tr.attrib['extremite_aval'], sep=" ")

        nodes[up_nid].append(up_coord)
        nodes[down_nid].append(down_coord)

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
            links[lid] = {'UPSTREAM': up_nid, 'DOWNSTREAM': down_nid, 'ID': lid, 'LENGTH':None}

    nodes = {n: np.mean(pos, axis=0) for n, pos in nodes.items()}

    G = MultiModalGraph()
    flow_graph = G.flow_graph

    [flow_graph.add_node(n, pos) for n, pos in nodes.items()]
    for l in links.values():
        try:
            flow_graph.add_link(l['ID'], l['UPSTREAM'], l['DOWNSTREAM'], length=l['LENGTH'])
        except AssertionError:
            rootlogger.warning(f"Skipping troncon: {l['ID']}, nodes {(l['UPSTREAM'], l['DOWNSTREAM'])} already connected")


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
    rootlogger.info(f"Number of nodes: {G.flow_graph.nb_nodes}")
    rootlogger.info(f"Number of links: {G.flow_graph.nb_links}")

    fig, ax = plt.subplots()
    draw_flow_graph(ax, G.flow_graph, node_label=False)
    plt.show()

    save_graph(G, file.replace('.xml', '.json'))


if __name__ == "__main__":
    rootlogger.setLevel(LOGLEVEL.INFO)
    convert_symuflow_to_mmgraph("/Users/florian.gacon/Work/MnMS/script/Lyon_symuviainput_1.xml")