from mnms.tools.io import load_graph
from mnms.tools.render import draw_multimodal_graph
from mnms.graph.algorithms import compute_shortest_path
from mnms.graph.path import reconstruct_path
from mnms.log import LOGLEVEL, rootlogger

import matplotlib.pyplot as plt

rootlogger.setLevel(LOGLEVEL.INFO)

mmgraph = load_graph('Network_v2_test_withreservedlanes.json')
mmgraph.add_zone('Res', [link.id for link in mmgraph.flow_graph.links.values()])

cost, path = compute_shortest_path(mmgraph, "E_OE_2", "E_SN_4", cost='length')
print(f"Cost of the path: {cost}")

reconstructed_path = reconstruct_path(mmgraph, path)
print("Reconstructed path:")
for p in reconstructed_path:
    print(p)


fig, ax = plt.subplots()
draw_multimodal_graph(ax, mmgraph, linkwidth=2, nodesize=6, dy=1500, node_label=False)
plt.show()