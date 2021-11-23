'''
Implement a xml parser of symuflow input to get a MultiModdalGraph
'''

from lxml import etree
from collections import defaultdict
import numpy as np
import matplotlib.pyplot as plt

from mnms.graph import MultiModalGraph
from mnms.tools.io import save_graph
from mnms.graph.render import draw_flow_graph, draw_mobility_service


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
        links[lid] = (up_nid, down_nid)

    nodes = {n: np.mean(pos, axis=0) for n, pos in nodes.items()}

    G = MultiModalGraph()
    flow_graph = G.flow_graph

    [flow_graph.add_node(n, pos) for n, pos in nodes.items()]
    [flow_graph.add_link(l, *n) for l, n in links.items()]


    line_elem = root.xpath("/ROOT_SYMUBRUIT/RESEAUX/RESEAU/PARAMETRAGE_VEHICULES_GUIDES/LIGNES_TRANSPORT_GUIDEES")[0]
    for line in line_elem.iter('LIGNE_TRANSPORT_GUIDEE'):
        lid = line.attrib['id']
        service = G.add_mobility_service(lid)
        service_nodes = set()
        service_links = dict()
        service_stops = list()
        for link in line.iter("TRONCON"):
            unode, dnode = links[link.attrib['id']]
            service_nodes.add(unode)
            service_nodes.add(dnode)
            service_links[link.attrib['id']] = (unode, dnode)

        arret_elem = root.xpath("/ROOT_SYMUBRUIT/RESEAUX/RESEAU/PARAMETRAGE_VEHICULES_GUIDES/ARRETS")[0]
        for arret in arret_elem.iter('ARRET'):
            if arret.attrib['lignes'] == lid:
                service_stops.append(arret.attrib['troncon'])

        [service.add_node(service_links[s][0]) for s in service_stops]
        [service.add_link(s, service_links[s][0],
                          service_links[s][1],
                          costs={'length':np.linalg.norm(flow_graph.nodes[service_links[s][0]].pos-flow_graph.nodes[service_links[s][1]].pos)},
                          reference_links=[s]) for s in service_stops]

    for outer_sid, outer_serv in G._mobility_services.items():
        for inner_sid, inner_serv in G._mobility_services.items():
            if outer_sid != inner_sid:
                for n in outer_serv.nodes.intersection(inner_serv.nodes):
                    G.connect_mobility_service(outer_sid, inner_sid, n, {"length":0})

    fig, ax = plt.subplots()
    draw_flow_graph(ax, G.flow_graph)
    for sid, serv in G._mobility_services.items():
        if sid != 'CAR':
            draw_mobility_service(ax, G, sid, np.random.rand(3), linkwidth=3)
    plt.show()

    save_graph(G, file.replace('.xml', '.json'))


if __name__ == "__main__":
    convert_symuflow_to_mmgraph("/Users/florian.gacon/Work/DIT4TRAM/script/Network_v2_test_withreservedlanes.xml")