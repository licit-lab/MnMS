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



def draw_flow_graph(ax, G, color='black', linkwidth=1, nodesize=5, node_label=True):
    lines = list()

    # for u in G.nodes:
    #     for v in G.get_node_neighbors(u):
    #         lines.append([G.nodes[u].pos, G.nodes[v].pos])

    for unode, dnode in G.links:
        lines.append([G.nodes[unode].pos, G.nodes[dnode].pos])


    line_segment = LineCollection(lines, linestyles='solid', colors=color, linewidths=linkwidth)
    ax.add_collection(line_segment)
    # try:
    x, y = zip(*[n.pos for n in G.nodes.values()])
    # except:
    #     print(G.nodes)
        # raise KeyboardInterrupt
    ax.plot(x, y, 'o', markerfacecolor='white', markeredgecolor=color, fillstyle='full', markersize=nodesize)

    if node_label:
        [ax.annotate(n.id, n.pos) for n in G.nodes.values()]

    ax.margins(0.05, 0.05)
    ax.axis("equal")
    plt.tight_layout()


def draw_mobility_service(ax, mmgraph, service, color, linkwidth=1, nodesize=5):
    # nodes = [graph.flow_graph.nodes[n.replace(f'{service}_', '')].id for n in graph._mobility_services[service].nodes if n.replace(f'{service}_', '') in graph.flow_graph.nodes]
    # subgraph = graph.flow_graph.extract_subgraph(nodes)
    # draw_flow_graph(ax, subgraph, color, linkwidth, nodesize)

    lines = list()
    for (unode, dnode) in mmgraph._mobility_services[service].links:
        link = mmgraph.mobility_graph.links[(service+'_'+unode, service+'_'+dnode)]
        for lid in link.reference_links:
            unode, dnode  = mmgraph.flow_graph._map_lid_nodes[lid]
            lines.append([mmgraph.flow_graph.nodes[unode].pos, mmgraph.flow_graph.nodes[dnode].pos])

    line_segment = LineCollection(lines, linestyles='solid', colors=color, linewidths=linkwidth)
    ax.add_collection(line_segment)
