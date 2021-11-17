import matplotlib.pyplot as plt

from routeservice.graph.graph import Node, MultiLayerGraph
from routeservice.graph.render import draw_multi_layer_graph


G = MultiLayerGraph()
gbus = G.create_layer("Bus")
gcar = G.create_layer("Car")
# gbike = G.create_layer("Bike")

n1 = Node('1', [0, 0])
n2 = Node('2', [1, 0])
n3 = Node('3', [1, 1])
n4 = Node('4', [0, 1])
n5 = Node('5', [1.5, 0.5])

gcar.add_node(n1)
gcar.add_node(n2)
gcar.add_node(n3)
gcar.add_node(n4)
gcar.add_node(n5)

gcar.add_link("1", "2", costs={"time": 10})
gcar.add_link("2", "3")
gcar.add_link("4", "3")
gcar.add_link("1", "4")
gcar.add_link("2", "5")
gcar.add_link("3", "5")

n6 = Node('6', [0, 0])
n7 = Node('7', [1, 1])
n8 = Node('8', [1.5, 0.5])

gbus.add_node(n6)
gbus.add_node(n7)
gbus.add_node(n8)

gbus.add_link("6", "7")
gbus.add_link("7", "8")

G.connect_layer(n1, n6)
G.connect_layer(n5, n8)
#
# n9 = Node('9', [1, 1])
# n10 = Node('10', [1.5, 0.5])

# gbike.add_node(n9)
# gbike.add_node(n10)

# gbike.add_link('9', '10')

print(G._connected_layers)

fig, ax = plt.subplots(figsize=(16, 9))
draw_multi_layer_graph(ax, G, linewidth=2)
plt.show()