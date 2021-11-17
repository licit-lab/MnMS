from itertools import cycle

import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D

import numpy as np

def draw_graph(ax, G, color='black', linkwidth=1, nodesize=5):
    lines = list()

    for u in G.nodes:
        for v in G.get_node_neighbors(u):
            lines.append([G.nodes[u].pos, G.nodes[v].pos])

    line_segment = LineCollection(lines, linestyles='solid', colors=color, linewidths=linkwidth)
    ax.add_collection(line_segment)

    x, y = zip(*[n.pos for n in G.nodes.values()])
    ax.plot(x, y, 'o', markerfacecolor='white', markeredgecolor=color, fillstyle='full', markersize=nodesize)

    ax.margins(0.05, 0.05)
    ax.axis("equal")
    plt.tight_layout()


def draw_multi_layer_graph(ax, G, linewidth=1, nodesize=5):
    colors = cycle(['#6CBE45', '#FF6319', '#0039A6', '#996633', '#808183'])
    nb_layer = len(G.layers)
    counter = nb_layer -1
    custom_legend = []
    for layerid, layer in G.layers.items():
        c = next(colors)
        subgraph = G.graph.extract_subgraph(layer.nodes)
        draw_graph(ax, subgraph, color=c, linkwidth=linewidth+counter*3, nodesize=nodesize+counter*5)
        counter -= 1
        custom_legend.append(Line2D([0], [0], color=c, lw=2))
    ax.legend(custom_legend, list(G.layers.keys()))


if __name__ == '__main__':
    from routeservice.graph.graph import Node, MultiLayerGraph

    G = MultiLayerGraph()
    gbus = G.create_layer("Bus")
    gcar = G.create_layer("Car")
    gbike = G.create_layer("Bike")

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

    gcar.add_link("1", "2")
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

    n9 = Node('9', [1, 1])
    n10 = Node('10', [1.5, 0.5])

    gbike.add_node(n9)
    gbike.add_node(n10)

    gbike.add_link('9', '10')

    print(G._connected_layers)


    fig, ax = plt.subplots(figsize=(16, 9))
    draw_multi_layer_graph(ax, G, linewidth=2)
    plt.show()