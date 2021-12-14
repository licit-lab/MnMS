from itertools import cycle

import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.lines import Line2D
import matplotlib.colors as mcolors

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


def draw_mobility_service(ax, mmgraph, service, color, linkwidth=1, nodesize=5, node_label=False):
    # nodes = [graph.flow_graph.nodes[n.replace(f'{service}_', '')].id for n in graph._mobility_services[service].nodes if n.replace(f'{service}_', '') in graph.flow_graph.nodes]
    # subgraph = graph.flow_graph.extract_subgraph(nodes)
    # draw_flow_graph(ax, subgraph, color, linkwidth, nodesize)

    lines = list()
    nodes = set()
    for (unode, dnode) in mmgraph._mobility_services[service].links:
        link = mmgraph.mobility_graph.links[(service+'_'+unode, service+'_'+dnode)]
        for lid in link.reference_links:
            unode, dnode  = mmgraph.flow_graph._map_lid_nodes[lid]
            nodes.add(unode)
            nodes.add(dnode)
            lines.append([mmgraph.flow_graph.nodes[unode].pos, mmgraph.flow_graph.nodes[dnode].pos])

    line_segment = LineCollection(lines, linestyles='solid', colors=color, linewidths=linkwidth)
    ax.add_collection(line_segment)

    x, y = zip(*[mmgraph.flow_graph.nodes[n].pos for n in nodes])
    ax.plot(x, y, 'o', markerfacecolor='white', markeredgecolor=color, fillstyle='full', markersize=nodesize)

    if node_label:
        [ax.annotate(n, mmgraph.flow_graph.nodes[n].pos) for n in nodes]


def draw_multimodal_graph(ax, mmgraph, linkwidth=1, nodesize=5, node_label=True, dy=0.4, defo_scale=0.25):
    flow_graph= mmgraph.flow_graph

    lines = list()
    deformation_matrix = np.array([[1, defo_scale], [0, defo_scale]])
    defo_app = lambda x: deformation_matrix.dot(x)

    for unode, dnode in flow_graph.links:
        lines.append([defo_app(flow_graph.nodes[unode].pos), defo_app(flow_graph.nodes[dnode].pos)])

    line_segment = LineCollection(lines, linestyles='solid', colors='black', linewidths=linkwidth)
    ax.add_collection(line_segment)
    x, y = zip(*[defo_app(n.pos) for n in flow_graph.nodes.values()])

    ax.plot(x, y, 'o', markerfacecolor='white', markeredgecolor='black', fillstyle='full', markersize=nodesize)

    if node_label:
        [ax.annotate(n.id, defo_app(n.pos)) for n in flow_graph.nodes.values()]

    ax.margins(0.05, 0.05)
    ax.axis("equal")

    all_color = list(mcolors.BASE_COLORS.keys())
    all_color.remove('w')
    colors = cycle(all_color)
    yshift = dy

    service_shift = dict()
    custom_legend = []
    for sid, service in mmgraph._mobility_services.items():
        c = next(colors)
        custom_legend.append(Line2D([0], [0], color=c, lw=2))
        defo_app = lambda x: deformation_matrix.dot(x) + [0, yshift]
        lines = list()
        nodes = set()
        for (unode, dnode) in service.links:
            link = mmgraph.mobility_graph.links[(sid + '_' + unode, sid + '_' + dnode)]
            nodes.add(unode)
            nodes.add(dnode)
            for lid in link.reference_links:
                unode, dnode = mmgraph.flow_graph._map_lid_nodes[lid]
                lines.append(
                    [defo_app(mmgraph.flow_graph.nodes[unode].pos), defo_app(mmgraph.flow_graph.nodes[dnode].pos)])

        line_segment = LineCollection(lines, linestyles='solid', colors=c, linewidths=linkwidth)
        ax.add_collection(line_segment)

        x, y = zip(*[defo_app(mmgraph.flow_graph.nodes[n].pos) for n in nodes])
        ax.plot(x, y, 'o', markerfacecolor='white', markeredgecolor=c, fillstyle='full', markersize=nodesize)

        if node_label:
            [ax.annotate(n, defo_app(mmgraph.flow_graph.nodes[n].pos)) for n in nodes]

        service_shift[sid] = yshift
        yshift += dy

    lines = list()
    for (upserv, downserv), nodes in mmgraph._connection_services.items():
        for n in nodes:
            pos = deformation_matrix.dot(mmgraph.flow_graph.nodes[n].pos)
            lines.append([pos + [0, service_shift[upserv]], pos + [0, service_shift[downserv]]])

    line_segment = LineCollection(lines, linestyles='dashed', colors='black', linewidths=linkwidth, alpha=0.3)
    ax.add_collection(line_segment)
    ax.legend(custom_legend, list(mmgraph._mobility_services.keys()))
    plt.tight_layout()