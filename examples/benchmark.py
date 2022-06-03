import matplotlib.pyplot as plt

from mnms.graph.generation import manhattan
from mnms.graph.shortest_path import dijkstra
from mnms.tools.render import draw_flow_graph

from mnms.mobility_service.car import CarMobilityGraphLayer

mmgraph = manhattan(10, 1)

# fig, ax = plt.subplots()
# draw_flow_graph(ax, mmgraph.flow_graph)

car_layer = CarMobilityGraphLayer()

for nid in mmgraph.flow_graph.nodes:
    car_layer.create_node(nid, nid)

for lid, link in mmgraph.flow_graph.sections.items():
    car_layer.create_link(lid, link.upstream, link.downstream, [lid], {'length':link.length})


path = dijkstra(car_layer.graph, 'NORTH_0', 'EAST_0', 'length', ['Car'])





