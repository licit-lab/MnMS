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
    print(nodes)

    G = MultiModalGraph()
    flow_graph = G.flow_graph

    [flow_graph.add_node(n, pos) for n, pos in nodes.items()]
    [flow_graph.add_link(l, *n) for l, n in links.items()]


    line_elem = root.xpath("/ROOT_SYMUBRUIT/RESEAUX/RESEAU/PARAMETRAGE_VEHICULES_GUIDES/LIGNES_TRANSPORT_GUIDEES")[0]
    for line in line_elem.iter('LIGNE_TRANSPORT_GUIDEE'):
        lid = line.attrib['id']
        service = G.add_mobility_service(lid)
        print(lid)
        for link in line.iter("TRONCON"):
            print(link.attrib['id'])
            unode, dnode = links[link.attrib['id']]
            service.add_node(unode)
            service.add_node(dnode)
            service.add_link(link.attrib['id'], unode, dnode,
                             costs={'length':np.linalg.norm(flow_graph.nodes[unode].pos-flow_graph.nodes[dnode].pos)},
                             reference_links=[link.attrib['id']])

    # for sid, serv in G._mobility_services.items():
    #     print(sid)

    car_service = G.add_mobility_service("CAR")
    [car_service.add_node(n) for n in nodes.keys()]
    [car_service.add_link(lid, unode, dnode, costs={'length':np.linalg.norm(flow_graph.nodes[unode].pos-flow_graph.nodes[dnode].pos)}, reference_links=[lid]) for lid, (unode, dnode) in links.items()]



    # fig, ax = plt.subplots()
    # draw_flow_graph(ax, G.flow_graph)
    # for sid, serv in G._mobility_services.items():
    #     print(sid, np.random.rand(3))
    #     draw_mobility_service(ax, G, sid, np.random.rand(3))
    # plt.show()

    save_graph(G, file.replace('.xml', '.json'))






if __name__ == "__main__":
    convert_symuflow_to_mmgraph("/Users/florian.gacon/Work/DIT4TRAM/script/Network_v2_test_withreservedlanes.xml")