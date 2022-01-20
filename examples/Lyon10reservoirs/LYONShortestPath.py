import os

import matplotlib.pyplot as plt

from mnms.graph.io import load_graph
from mnms.tools.render import draw_flow_graph, draw_path
from mnms.mobility_service import BaseMobilityService
from mnms.graph.algorithms import compute_shortest_path_nodes
from mnms.log import rootlogger, LOGLEVEL
from mnms.demand.user import User
from mnms.tools.time import Time

rootlogger.setLevel(LOGLEVEL.INFO)

input_graph = os.path.dirname(os.path.abspath(__file__)) + '/Lyon_symuviainput_1.json'
mmgraph = load_graph(input_graph)
rootlogger.info(f"Nodes: {len(mmgraph.flow_graph.nodes)}")
rootlogger.info(f"Links: {len(mmgraph.flow_graph.links)}")

car = BaseMobilityService('Car', 10)

for node in mmgraph.flow_graph.nodes.values():
    car.add_node(node.id, node.id)


for link in mmgraph.flow_graph.links.values():
    car.add_link(link.id,
                 link.upstream_node,
                 link.downstream_node,
                 costs={'length': link.length},
                 reference_links=link.id)

mmgraph.add_mobility_service(car)


user = User('0', "E_82610778_T_58239512_FRef", "C_TRAM_535", Time("07:00:00"))
cost = compute_shortest_path_nodes(mmgraph, user, algorithm="astar")


fig, ax = plt.subplots()
draw_flow_graph(ax, mmgraph.flow_graph, node_label=False)
draw_path(ax, mmgraph, user.path)
plt.show()






