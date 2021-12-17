import os

import matplotlib.pyplot as plt

from mnms.tools.io import load_graph
from mnms.tools.render import draw_flow_graph, draw_path
from mnms.mobility_service import BaseMobilityService
from mnms.graph.algorithms import compute_shortest_path
from mnms.log import logger, LOGLEVEL

logger.setLevel(LOGLEVEL.INFO)

input_graph = os.path.dirname(os.path.abspath(__file__)) + '/Lyon_symuviainput_1.json'
mmgraph = load_graph(input_graph)
logger.info(f"Nodes: {len(mmgraph.flow_graph.nodes)}")
logger.info(f"Links: {len(mmgraph.flow_graph.links)}")

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

cost, path = compute_shortest_path(mmgraph, "E_82610778_T_58239512_FRef", "C_TRAM_535", algorithm="astar")


fig, ax = plt.subplots()
draw_flow_graph(ax, mmgraph.flow_graph, node_label=False)
draw_path(ax, mmgraph, path)
plt.show()






